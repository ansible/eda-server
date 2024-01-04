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

from .user import User

__all__ = ("BaseActivation",)


class BaseActivation(models.Model):
    """Base model for activations."""

    name = models.TextField(null=False, unique=True)
    description = models.TextField(default="")
    is_enabled = models.BooleanField(default=True)
    # TODO(alex) Since local activations are no longer supported
    # this field should be mandatory.
    decision_environment = models.ForeignKey(
        "DecisionEnvironment", on_delete=models.SET_NULL, null=True
    )
    restart_policy = models.TextField(
        choices=RestartPolicy.choices(),
        default=RestartPolicy.ON_FAILURE,
    )
    status = models.TextField(
        choices=ActivationStatus.choices(),
        default=ActivationStatus.PENDING,
    )
    # TODO: this field should be no longer needed
    current_job_id = models.TextField(null=True)
    restart_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)  # internal, since last good
    # TODO: this field should be no longer needed
    is_valid = models.BooleanField(default=False)  # internal, passed first run
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)
    status_updated_at = models.DateTimeField(null=True)
    status_message = models.TextField(null=True, default=None)
    latest_instance = models.OneToOneField(
        "ActivationInstance",
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # when creating
        if self._state.adding:
            if self.status_message is None:
                self._set_status_message()
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
                self._set_status_message()
                kwargs["update_fields"].append("status_message")

        super().save(*args, **kwargs)

    def _set_status_message(self):
        self.status_message = self._get_default_status_message()

        if self.status == ActivationStatus.PENDING and not self.is_enabled:
            self.status_message = "Activation is marked as disabled"

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
        self.status_updated_at = models.functions.Now()
        update_fields = [
            "status",
            "status_updated_at",
            "modified_at",
        ]
        if status_message:
            self.status_message = status_message
            update_fields.append("status_message")
        self.save(
            update_fields=update_fields,
        )
