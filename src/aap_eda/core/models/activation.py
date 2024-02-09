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
import uuid

import yaml
from django.conf import settings
from django.db import models

from aap_eda.core.enums import ActivationStatus, RestartPolicy
from aap_eda.services.activation.engine.common import ContainerableMixin

from .credential import Credential
from .mixins import StatusHandlerModelMixin
from .user import AwxToken, User

__all__ = ("Activation",)


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
    event_streams = models.ManyToManyField(
        "EventStream",
        default=None,
    )

    # Implementation of the ContainerableMixin.
    def get_command_line_parameters(self) -> dict[str, tp.Any]:
        params = super().get_command_line_parameters()
        return params | {}

    def get_container_parameters(self) -> dict[str, tp.Any]:
        params = super().get_container_parameters()
        return params | {
            "activation_id": self.id,
            "activation_instance_id": self.latest_instance.id,
        }

    def get_restart_policy(self) -> str:
        return self.restart_policy

    def validate(self):
        pass

    def _get_context(self) -> dict[str, tp.Any]:
        if self.extra_var:
            context = yaml.safe_load(self.extra_var.extra_var)
        else:
            context = {}
        return context

    def _get_image_credential(self) -> tp.Optional[Credential]:
        return self.decision_environment.credential

    def _get_image_url(self) -> str:
        return self.decision_environment.image_url

    def _get_name(self) -> str:
        return (
            f"{settings.CONTAINER_NAME_PREFIX}-{self.latest_instance.id}"
            f"-{uuid.uuid4()}"
        )

    def _get_rulebook_rulesets(self) -> str:
        return self.rulebook_rulesets
