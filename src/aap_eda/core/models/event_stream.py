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

import enum

from django.conf import settings
from django.core import validators
from django.db import models

from aap_eda.core.enums import (
    ActivationStatus,
    RestartPolicy,
    RulebookProcessLogLevel,
)
from aap_eda.core.utils import get_default_log_level
from aap_eda.services.activation.engine.common import ContainerableMixin

from .mixins import StatusHandlerModelMixin


class RestartCompletionInterval(enum.IntEnum):
    MINIMUM = 0
    SETTINGS = MINIMUM
    DEFAULT = SETTINGS


class RestartFailureInterval(enum.IntEnum):
    MINIMUM = 0
    SETTINGS = MINIMUM
    DEFAULT = SETTINGS


class RestartFailureLimit(enum.IntEnum):
    MINIMUM = -1
    SETTINGS = 0
    DEFAULT = SETTINGS
    UNLIMITED = MINIMUM


class EventStream(StatusHandlerModelMixin, ContainerableMixin, models.Model):
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
    restart_completion_interval = models.IntegerField(
        validators=[
            validators.MinValueValidator(
                limit_value=RestartCompletionInterval.MINIMUM,
                message="The restart interval for completions specifies"
                " the delay, in seconds, between restarts"
                "; it must be an integer greater than or equal to"
                f" {RestartCompletionInterval.MINIMUM}"
                f"; system settings = {RestartCompletionInterval.SETTINGS}"
                f", default = {RestartCompletionInterval.DEFAULT}",
            ),
        ],
        default=RestartCompletionInterval.DEFAULT,
    )
    restart_failure_interval = models.IntegerField(
        validators=[
            validators.MinValueValidator(
                limit_value=RestartFailureInterval.MINIMUM,
                message="The restart interval for failures specifies"
                " the delay, in seconds, between restarts"
                "; it must be an integer greater than or equal to "
                f" {RestartFailureInterval.MINIMUM}"
                f"; system settings = {RestartFailureInterval.SETTINGS}"
                f", default = {RestartFailureInterval.DEFAULT}",
            ),
        ],
        default=RestartFailureInterval.DEFAULT,
    )
    restart_failure_limit = models.IntegerField(
        validators=[
            validators.MinValueValidator(
                limit_value=RestartFailureLimit.MINIMUM,
                message="The restart limit for failiures specifies"
                " the limit on repeated attempts to start an activation"
                " in the face of failures to do so"
                "; it must be an integer greater than or equal to"
                f" {RestartFailureLimit.MINIMUM}"
                f"; system settings = {RestartFailureLimit.SETTINGS}"
                f", unlimited restarts = {RestartFailureLimit.UNLIMITED}"
                f", default = {RestartFailureLimit.DEFAULT}",
            ),
        ],
        default=RestartFailureLimit.DEFAULT,
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
    channel_name = models.TextField(null=True, default=None)
    source_type = models.TextField(null=False)
    source_args = models.JSONField(null=True, default=None)
    log_level = models.CharField(
        max_length=20,
        choices=RulebookProcessLogLevel.choices(),
        default=get_default_log_level,
    )

    class Meta:
        db_table = "core_event_stream"
        indexes = [
            models.Index(fields=["name"], name="ix_event_stream_name"),
        ]
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"EventStream {self.name} ({self.id})"

    # Implementation of the ContainerableMixin.
    def _get_skip_audit_events(self) -> bool:
        """Event stream skips audit events."""
        return True

    @property
    def effective_restart_completion_interval(self):
        effective = self.restart_completion_interval
        if effective == RestartCompletionInterval.SETTINGS:
            effective = settings.ACTIVATION_RESTART_SECONDS_ON_COMPLETE
        return effective

    @property
    def effective_restart_failure_interval(self):
        effective = self.restart_failure_interval
        if effective == RestartFailureInterval.SETTINGS:
            effective = settings.ACTIVATION_RESTART_SECONDS_ON_FAILURE
        return effective

    @property
    def effective_restart_failure_limit(self):
        effective = self.restart_failure_limit
        if effective == RestartFailureLimit.SETTINGS:
            effective = settings.ACTIVATION_MAX_RESTARTS_ON_FAILURE
        return effective

    @property
    def unlimited_restart_failures(self):
        return self.restart_failure_limit == RestartFailureLimit.UNLIMITED
