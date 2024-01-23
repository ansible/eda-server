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

import typing as tp

from django.db import models

from aap_eda.core.enums import (
    ActivationStatus,
    RestartPolicy,
)

from .mixins import StatusHandlerModelMixin, ProcessParentValidatorMixin

__all__ = (
    "Activation",
    "ActivationInstance",
    "ActivationInstanceLog",
)


# WARNING: There is shared logic between this model and the
# Source model. Keep it in mind when changing this model.
class Activation(StatusHandlerModelMixin, models.Model):
    """Model for Rulebook activations."""

    name = models.TextField(null=False, unique=True)
    description = models.TextField(default="")
    is_enabled = models.BooleanField(default=True)
    git_hash = models.TextField(null=False, default="")
    # TODO(alex) Since local activations are no longer supported
    # this field should be mandatory.
    decision_environment = models.ForeignKey(
        "DecisionEnvironment", on_delete=models.SET_NULL, null=True
    )
    project = models.ForeignKey(
        "Project", on_delete=models.SET_NULL, null=True
    )
    # TODO(alex): this field should be mandatory.
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
    # TODO(alex): name and rulesets should be populated in the model, not in
    # the serializer.
    rulebook_name = models.TextField(
        null=False,
        help_text="Name of the referenced rulebook",
    )
    rulebook_rulesets = models.TextField(
        null=False,
        help_text="Content of the last referenced rulebook",
    )
    ruleset_stats = models.JSONField(default=dict)
    user = models.ForeignKey("User", on_delete=models.CASCADE, null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)
    status_updated_at = models.DateTimeField(null=True)
    status_message = models.TextField(null=True, default=None)
    # TODO(alex) This field could be a property
    latest_instance = models.OneToOneField(
        "ActivationInstance",
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    awx_token = models.ForeignKey(
        "AwxToken",
        on_delete=models.SET_NULL,
        null=True,
        default=None,
    )
    sources = models.ManyToManyField(
        "Source",
        default=None,
    )

    class Meta:
        db_table = "core_activation"
        indexes = [models.Index(fields=["name"], name="ix_activation_name")]
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.name} ({self.id})"


class ActivationInstance(
    ProcessParentValidatorMixin,
    StatusHandlerModelMixin,
    models.Model,
):
    """Model for activation instances."""

    name = models.TextField(null=False, default="")
    status = models.TextField(
        choices=ActivationStatus.choices(),
        default=ActivationStatus.PENDING,
    )
    git_hash = models.TextField(null=False, default="")

    # Source and activation will be completely different models
    # Since for now are only two, two foreign keys are enough
    # If more are added, a generic relation might be considered
    # In this way the relation is clear and simple without the
    # tradeoffs of a generic relation
    # Ref: https://docs.djangoproject.com/en/4.2/ref/contrib/contenttypes/#generic-relations
    activation = models.ForeignKey(
        "Activation",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="activation_processes",
    )
    source = models.ForeignKey(
        "Source",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="source_processes",
    )
    started_at = models.DateTimeField(auto_now_add=True, null=False)
    updated_at = models.DateTimeField(null=True)
    ended_at = models.DateTimeField(null=True)
    activation_pod_id = models.TextField(null=True)
    status_message = models.TextField(null=True, default=None)
    log_read_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "core_activation_instance"
        ordering = ("-started_at",)

    def __str__(self):
        return f"{self.name} ({self.id})"

    def save(self, *args, **kwargs):
        parent = getattr(self, "activation", None) or getattr(
            self,
            "source",
            None,
        )
        if not parent:
            raise ValueError(
                "ActivationInstance must have either activation or source"
            )

        # populate latest_instance when creating
        if self._state.adding:
            # TODO(alex): parent.latest_instance can a be a property
            # and returns the most recent instance
            parent.latest_instance = self

        super().save(*args, **kwargs)
        parent.save(update_fields=["latest_instance"])

    def update_status(
        self, status: ActivationStatus, status_message: tp.Optional[str] = None
    ) -> None:
        self.status = status
        self.updated_at = models.functions.Now()
        update_fields = [
            "status",
            "updated_at",
        ]
        if status_message:
            self.status_message = status_message
            update_fields.append("status_message")

        if status in [
            ActivationStatus.STOPPED,
            ActivationStatus.COMPLETED,
            ActivationStatus.FAILED,
            ActivationStatus.ERROR,
        ]:
            self.ended_at = models.functions.Now()
            update_fields.append("ended_at")

        self.save(
            update_fields=update_fields,
        )


class ActivationInstanceLog(models.Model):
    class Meta:
        db_table = "core_activation_instance_log"

    activation_instance = models.ForeignKey(
        "ActivationInstance", on_delete=models.CASCADE
    )
    line_number = models.IntegerField()
    log = models.TextField()
