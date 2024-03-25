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
from .user import AwxToken, User

__all__ = ("Activation",)


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


class RetentionFailurePeriod(enum.IntEnum):
    MINIMUM = -1
    SETTINGS = 0
    DEFAULT = SETTINGS
    FOREVER = MINIMUM


class RetentionSuccessPeriod(enum.IntEnum):
    MINIMUM = -1
    SETTINGS = 0
    DEFAULT = SETTINGS
    FOREVER = MINIMUM


class Activation(StatusHandlerModelMixin, ContainerableMixin, models.Model):
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

    retention_failure_period = models.IntegerField(
        validators=[
            validators.MinValueValidator(
                limit_value=RetentionFailurePeriod.MINIMUM,
                message="The retention period for failiures specifies"
                " the length of time, in hours, an individual failure"
                "result will be retained"
                "; it must be an integer greater than or equal to"
                f" {RetentionFailurePeriod.MINIMUM}"
                f"; system settings = {RetentionFailurePeriod.SETTINGS}"
                f", forever = {RetentionFailurePeriod.FOREVER}"
                f", default = {RetentionFailurePeriod.DEFAULT}",
            ),
        ],
        default=RetentionFailurePeriod.DEFAULT,
    )
    retention_success_period = models.IntegerField(
        validators=[
            validators.MinValueValidator(
                limit_value=RetentionSuccessPeriod.MINIMUM,
                message="The retention period for successes specifies"
                " the length of time, in hours, an individual success"
                "result will be retained"
                "; it must be an integer greater than or equal to"
                f" {RetentionSuccessPeriod.MINIMUM}"
                f"; system settings = {RetentionSuccessPeriod.SETTINGS}"
                f", forever = {RetentionSuccessPeriod.FOREVER}"
                f", default = {RetentionSuccessPeriod.DEFAULT}",
            ),
        ],
        default=RetentionSuccessPeriod.DEFAULT,
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
    event_streams = models.ManyToManyField(
        "EventStream",
        default=None,
    )
    log_level = models.CharField(
        max_length=20,
        choices=RulebookProcessLogLevel.choices(),
        default=get_default_log_level,
    )
    eda_credentials = models.ManyToManyField(
        "EdaCredential", related_name="activations", default=None
    )
    eda_system_vault_credential = models.OneToOneField(
        "EdaCredential",
        null=True,
        default=None,
        on_delete=models.CASCADE,
        related_name="+",
    )

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

    @property
    def effective_retention_failure_period(self):
        effective = self.retention_failure_period
        if effective == RetentionFailurePeriod.SETTINGS:
            effective = settings.ACTIVATION_RETENTION_FAILURE_HOURS
        if effective != RetentionFailurePeriod.FOREVER:
            effective *= 3600
        return effective

    @property
    def effective_retention_success_period(self):
        effective = self.retention_success_period
        if effective == RetentionSuccessPeriod.SETTINGS:
            effective = settings.ACTIVATION_RETENTION_SUCCESS_HOURS
        if effective != RetentionSuccessPeriod.FOREVER:
            effective *= 3600
        return effective
