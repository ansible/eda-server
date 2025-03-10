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

from aap_eda.core.enums import (
    ActivationStatus,
    ProcessParentType,
    RestartPolicy,
    RulebookProcessLogLevel,
)
from aap_eda.core.utils import get_default_log_level
from aap_eda.services.activation.engine.common import ContainerableMixin

from .base import BaseOrgModel, PrimordialModel, UniqueNamedModel
from .event_stream import EventStream
from .mixins import OnDeleteProcessParentMixin, StatusHandlerModelMixin
from .user import AwxToken, User

__all__ = ("Activation",)

DEFAULT_ENABLED = True


class Activation(
    StatusHandlerModelMixin,
    ContainerableMixin,
    OnDeleteProcessParentMixin,
    BaseOrgModel,
    UniqueNamedModel,
    PrimordialModel,
):
    class Meta:
        db_table = "core_activation"
        indexes = [models.Index(fields=["name"], name="ix_activation_name")]
        ordering = ("-created_at",)
        permissions = [
            ("enable_activation", "Can enable an activation"),
            ("disable_activation", "Can disable an activation"),
            ("restart_activation", "Can restart an activation"),
        ]
        default_permissions = ["add", "view", "change", "delete"]

    description = models.TextField(
        default="",
        blank=True,
    )
    is_enabled = models.BooleanField(default=DEFAULT_ENABLED)
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
    extra_var = models.TextField(null=True, blank=True)
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
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)
    edited_at = models.DateTimeField(null=True)
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
    k8s_service_name = models.TextField(
        null=True,
        default=None,
        blank=True,
        help_text="Name of the kubernetes service",
    )
    event_streams = models.ManyToManyField(
        EventStream, related_name="activations", default=None
    )
    source_mappings = models.TextField(
        default="",
        blank=True,
        help_text="Mapping between sources and event streams",
    )
    skip_audit_events = models.BooleanField(
        default=False,
        help_text=("Skip audit events for activation"),
    )

    def get_parent_type(self) -> str:
        return ProcessParentType.ACTIVATION

    def _get_skip_audit_events(self) -> bool:
        """Activation can optionally skip audit events."""
        return self.skip_audit_events
