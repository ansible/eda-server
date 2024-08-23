#  Copyright 2024 Red Hat, Inc.
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

from django.core.exceptions import ValidationError
from django.db import models

from aap_eda.core.enums import (
    ACTIVATION_STATUS_MESSAGE_MAP,
    ActivationStatus,
    ProcessParentType,
)
from aap_eda.core.exceptions import (
    StatusRequiredError,
    UnknownStatusError,
    UpdateFieldsRequiredError,
)

from .base import BaseOrgModel

__all__ = (
    "RulebookProcess",
    "RulebookProcessLog",
)


class RulebookProcess(BaseOrgModel):
    """Rulebook Process model.

    Rulebook Process is an instance of ansible-rulebook process
    that is created when an activation or event stream is started.
    """

    router_basename = "activationinstance"

    name = models.TextField(null=False, default="")
    status = models.TextField(
        choices=ActivationStatus.choices(),
        default=ActivationStatus.PENDING,
    )
    git_hash = models.TextField(null=False, default="")
    activation = models.ForeignKey(
        "Activation",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="activation_processes",
    )
    parent_type = models.TextField(
        choices=ProcessParentType.choices(),
        null=False,
        default=ProcessParentType.ACTIVATION,
    )
    started_at = models.DateTimeField(auto_now_add=True, null=False)
    updated_at = models.DateTimeField(null=True)
    ended_at = models.DateTimeField(null=True)
    # TODO: rename field to pod_id
    activation_pod_id = models.TextField(null=True)
    status_message = models.TextField(null=True, default=None)
    log_read_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "core_rulebook_process"
        ordering = ("-started_at",)
        default_permissions = ("view",)

    def __str__(self) -> str:
        return f"Rulebook Process id {self.id}"

    def save(self, *args, **kwargs):
        # when creating
        if self._state.adding:
            # ensure type is set
            self._set_parent_type()
            parent = self.get_parent()
            parent.latest_instance = self

            if self.status_message is None:
                self.status_message = self._get_default_status_message()
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

        # update parent's latest_instance
        parent = self.get_parent()
        parent.save(update_fields=["latest_instance"])

    def _check_parent(self):
        """Clean method for RulebookProcess model."""
        # Check that activation is set
        if self.activation is None:
            raise ValidationError("activation must be set")

    def get_parent(self):
        return getattr(self, self.parent_type.lower())

    def _set_parent_type(self):
        self._check_parent()
        if self.activation:
            self.parent_type = ProcessParentType.ACTIVATION

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

    def summary_fields(self):
        return {
            "id": self.id,
            "name": self.name,
        }


class RulebookProcessLog(models.Model):
    class Meta:
        db_table = "core_rulebook_process_log"

    # TODO(alex): this field should be renamed to rulebook_process
    # requires coordination with UI and QE teams.
    # Keep the old field for backward compatibility.
    activation_instance = models.ForeignKey(
        "RulebookProcess", on_delete=models.CASCADE
    )
    log = models.TextField()
    log_timestamp = models.BigIntegerField(null=False, default=0)


class RulebookProcessQueue(models.Model):
    """Rulebook Process Queue model.

    Rulebook Process Queue keeps track of the queue name for a
    Rulebook Process. Every rulebook process is associated with the
    queue, by name, where it ran at creation.
    """

    queue_name = models.CharField(max_length=255)
    process = models.OneToOneField(
        "RulebookProcess",
        on_delete=models.CASCADE,
        primary_key=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["queue_name"]),
        ]

    def __str__(self) -> str:
        return (
            f"Rulebook Process id {self.process.id} in queue {self.queue_name}"
        )
