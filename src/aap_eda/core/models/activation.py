#  Copyright 2022 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from django.db import models

from aap_eda.core.enums import ActivationStatus, RestartPolicy

from .eda_model_mixin import EDAModelMixin
from .user import User

__all__ = (
    "Activation",
    "ActivationInstance",
    "ActivationInstanceLog",
)


class Activation(EDAModelMixin, models.Model):
    class Meta:
        db_table = "core_activation"
        indexes = [models.Index(fields=["name"], name="ix_activation_name")]
        ordering = ("-created_at",)

    name = models.TextField(null=False, unique=True)
    description = models.TextField(default="")
    is_enabled = models.BooleanField(default=True)
    decision_environment = models.ForeignKey(
        "DecisionEnvironment", on_delete=models.SET_NULL, null=True
    )
    project = models.ForeignKey(
        "Project", on_delete=models.SET_NULL, null=True
    )
    rulebook = models.ForeignKey(
        "Rulebook", on_delete=models.SET_NULL, null=True
    )
    extra_var = models.ForeignKey(
        "ExtraVar", on_delete=models.CASCADE, null=True
    )
    restart_policy = models.TextField(
        choices=RestartPolicy.choices(),
        default=RestartPolicy.ON_FAILURE,
    )
    status = models.TextField(
        choices=ActivationStatus.choices(),
        default=ActivationStatus.PENDING,
    )
    current_job_id = models.TextField(null=True)
    restart_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)  # internal, since last good
    is_valid = models.BooleanField(default=False)  # internal, passed first run
    rulebook_name = models.TextField(
        null=False,
        help_text="Name of the referenced rulebook",
    )
    rulebook_rulesets = models.TextField(
        null=False,
        help_text="Content of the last referenced rulebook",
    )
    ruleset_stats = models.JSONField(default=dict)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)

    def destroying(self) -> None:
        self.status = ActivationStatus.DELETING
        self.save(update_fields=["status"])

    def pending(self) -> None:
        self.is_enabled = True
        self.failure_count = 0
        self.status = ActivationStatus.PENDING
        self.save(
            update_fields=[
                "is_enabled",
                "failure_count",
                "status",
                "modified_at",
            ]
        )

    def running(self) -> None:
        self.status = ActivationStatus.RUNNING
        self.save(update_fields=["status"])

    def starting(self) -> None:
        self.status = ActivationStatus.STARTING
        self.save(update_fields=["status"])

    def stopped(self) -> None:
        self.current_job_id = None
        self.status = ActivationStatus.STOPPED
        self.save()

    def stopping(self) -> bool:
        if not self.is_enabled:
            return False

        self.status = ActivationStatus.STOPPING
        self.is_enabled = False
        self.save(update_fields=["is_enabled", "status", "modified_at"])

        return True


class ActivationInstance(models.Model):
    class Meta:
        db_table = "core_activation_instance"
        ordering = ("-started_at",)

    name = models.TextField(null=False, default="")
    status = models.TextField(
        choices=ActivationStatus.choices(),
        default=ActivationStatus.PENDING,
    )
    activation = models.ForeignKey("Activation", on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True, null=False)
    updated_at = models.DateTimeField(null=True)
    ended_at = models.DateTimeField(null=True)
    activation_pod_id = models.TextField(null=True)

    def failed(self) -> None:
        self.status = ActivationStatus.FAILED
        self.save_with_activation(
            update_fields=["status", "ended_at", "updated_at"],
        )

    def save_with_activation(self, update_fields: list) -> None:
        """Save self and update the linked activation's status accordingly."""
        self.activation.status = self.status
        running_states = [
            ActivationStatus.PENDING.value,
            ActivationStatus.STARTING.value,
            ActivationStatus.RUNNING.value,
            ActivationStatus.UNRESPONSIVE.value,
        ]
        activation_fields = ["status", "modified_at"]
        if str(self.status) not in running_states:
            self.activation.current_job_id = None
            activation_fields.append("current_job_id")
        if str(self.status) == ActivationStatus.COMPLETED.value:
            self.activation.failure_count = 0
            activation_fields.append("failure_count")

        self.save(update_fields=update_fields)
        self.activation.save(update_fields=activation_fields)


class ActivationInstanceLog(models.Model):
    class Meta:
        db_table = "core_activation_instance_log"

    activation_instance = models.ForeignKey(
        "ActivationInstance", on_delete=models.CASCADE
    )
    line_number = models.IntegerField()
    log = models.TextField()
