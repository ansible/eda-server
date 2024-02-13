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

import uuid

from django.db import models

from aap_eda.core.enums import ActivationStatus, RestartPolicy

from .mixins import StatusHandlerModelMixin


class EventStream(StatusHandlerModelMixin, models.Model):
    """Model representing an event stream."""

    name = models.TextField(null=False, unique=True)
    description = models.TextField(default="")
    is_enabled = models.BooleanField(default=True)
    decision_environment = models.ForeignKey(
        "DecisionEnvironment",
        on_delete=models.SET_NULL,
        null=True,
    )
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
        "RulebookProcess",
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    uuid = models.UUIDField(default=uuid.uuid4)
    source_type = models.TextField(null=False)
    args = models.JSONField(null=True, default=None)
    listener_args = models.JSONField(null=True, default=None)

    class Meta:
        db_table = "core_event_stream"
        indexes = [
            models.Index(fields=["name"], name="ix_event_stream_name"),
        ]
        ordering = ("-created_at",)
        default_permissions = ('add', 'view',)

    def __str__(self) -> str:
        return f"EventStream {self.name} ({self.id})"
