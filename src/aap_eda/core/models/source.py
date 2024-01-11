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

import uuid

from django.db import models

from aap_eda.core.enums import ActivationStatus, RestartPolicy

from .mixins import StatusHandlerModelMixin

__all__ = ["Source"]


# WARNING: There is shared logic between this model and the
# Activation model. Keep it in mind when changing this model.
class Source(StatusHandlerModelMixin, models.Model):
    """Model for source listener."""

    name = models.TextField(null=False, unique=True)
    description = models.TextField(default="")
    is_enabled = models.BooleanField(default=True)
    decision_environment = models.ForeignKey(
        "DecisionEnvironment",
        on_delete=models.SET_NULL,
        null=True,
    )
    # TODO(alex): this field should be mandatory.
    rulebook = models.ForeignKey(
        "Rulebook",
        on_delete=models.SET_NULL,
        null=True,
    )
    extra_var = models.ForeignKey(
        "ExtraVar",
        on_delete=models.CASCADE,
        null=True,
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
    rulebook_name = models.TextField(
        null=False,
        help_text="Name of the referenced rulebook",
        default="",
    )
    rulebook_rulesets = models.TextField(
        null=False,
        help_text="Content of the last referenced rulebook",
        default="",
    )
    ruleset_stats = models.JSONField(default=dict)
    user = models.ForeignKey("User", on_delete=models.CASCADE, null=False)
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
    uuid = models.UUIDField(default=uuid.uuid4)
    type = models.TextField(null=False)
    args = models.JSONField(null=True, default=None)
    listener_args = models.JSONField(null=True, default=None)

    class Meta:
        db_table = "core_source"
        indexes = [
            models.Index(fields=["id"], name="ix_source_id"),
            models.Index(fields=["name"], name="ix_source_name"),
        ]

    def __str__(self):
        return f"{self.name} ({self.id})"
