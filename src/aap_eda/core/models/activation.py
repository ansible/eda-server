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
    ACTIVATION_STATUS_MESSAGE_MAP,
    ActivationStatus,
    RestartPolicy,
)
from aap_eda.core.exceptions import (
    StatusRequiredError,
    UnknownStatusError,
    UpdateFieldsRequiredError,
)

from .mixins import StatusHandlerModelMixin
from .organization import Organization
from .user import AwxToken, User

__all__ = (
    "Activation",
    "RulebookProcess",
    "RulebookProcessLog",
)


class Activation(StatusHandlerModelMixin, models.Model):
    class Meta:
        db_table = "core_activation"
        indexes = [models.Index(fields=["name"], name="ix_activation_name")]
        ordering = ("-created_at",)

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
    rulebook = models.ForeignKey(
        "Rulebook", on_delete=models.SET_NULL, null=True
    )
    extra_var = models.ForeignKey(
        "ExtraVar", on_delete=models.CASCADE, null=True
    )
    organization = models.ForeignKey(
        "Organization", on_delete=models.CASCADE, null=True
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)
    status_updated_at = models.DateTimeField(null=True)
    status_message = models.TextField(null=True, default=None)
    latest_instance = models.OneToOneField(
        "RulebookProcess",
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    awx_token = models.ForeignKey(
        AwxToken,
        on_delete=models.SET_NULL,
        null=True,
        default=None,
    )
    credentials = models.ManyToManyField(
        "Credential", related_name="activations", default=None
    )
    system_vault_credential = models.OneToOneField(
        "Credential",
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.organization:
            self.organization = Organization.objects.get_default()
            super().save(update_fields=["organization"])


class RulebookProcess(models.Model):
    class Meta:
        db_table = "core_rulebook_process"
        ordering = ("-started_at",)

    name = models.TextField(null=False, default="")
    status = models.TextField(
        choices=ActivationStatus.choices(),
        default=ActivationStatus.PENDING,
    )
    git_hash = models.TextField(null=False, default="")
    activation = models.ForeignKey("Activation", on_delete=models.CASCADE)
    organization = models.ForeignKey(
        "Organization", on_delete=models.CASCADE, null=True
    )
    started_at = models.DateTimeField(auto_now_add=True, null=False)
    updated_at = models.DateTimeField(null=True)
    ended_at = models.DateTimeField(null=True)
    activation_pod_id = models.TextField(null=True)
    status_message = models.TextField(null=True, default=None)
    log_read_at = models.DateTimeField(null=True)

    def save(self, *args, **kwargs):
        # when creating
        if self._state.adding:
            if self.status_message is None:
                self.status_message = self._get_default_status_message()

                # populate latest_instance of activation at creation
                self.activation.latest_instance = self
        else:
            if not bool(kwargs) or "update_fields" not in kwargs:
                raise UpdateFieldsRequiredError(
                    "update_fields is required to use when saving "
                    "due to race conditions"
                )
            else:
                if "status" in kwargs["update_fields"]:
                    self._is_valid_status()

            if (
                "status_message" in kwargs["update_fields"]
                and "status" not in kwargs["update_fields"]
            ):
                raise StatusRequiredError(
                    "status_message cannot be set by itself, "
                    "it requires status and status_message together"
                )
            # when updating without status_message
            elif (
                "status" in kwargs["update_fields"]
                and "status_message" not in kwargs["update_fields"]
            ):
                self.status_message = self._get_default_status_message()
                kwargs["update_fields"].append("status_message")

        super().save(*args, **kwargs)
        self.activation.save(update_fields=["latest_instance"])

        if not self.organization:
            self.organization = Organization.objects.get_default()
            super().save(update_fields=["organization"])

    def _get_default_status_message(self):
        try:
            return ACTIVATION_STATUS_MESSAGE_MAP[self.status]
        except KeyError:
            raise UnknownStatusError(f"Status [{self.status}] is invalid")

    def _is_valid_status(self):
        try:
            ActivationStatus(self.status)
        except ValueError as error:
            raise UnknownStatusError(error)

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


class RulebookProcessLog(models.Model):
    class Meta:
        db_table = "core_rulebook_process_log"

    # TODO(alex): this field should be renamed to rulebook_process
    # requires coordination with UI and QE teams.
    # Keep the old field for backward compatibility.
    activation_instance = models.ForeignKey(
        "RulebookProcess", on_delete=models.CASCADE
    )
    organization = models.ForeignKey(
        "Organization", on_delete=models.CASCADE, null=True
    )
    line_number = models.IntegerField()
    log = models.TextField()
    log_timestamp = models.BigIntegerField(null=False, default=0)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.organization:
            self.organization = Organization.objects.get_default()
            super().save(update_fields=["organization"])
