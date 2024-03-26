#  Copyright 2023 Red Hat, Inc.
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
import json
import logging
import secrets
import uuid
from typing import Union

import yaml
from rest_framework import serializers

from aap_eda.api.constants import (
    EDA_SERVER_VAULT_LABEL,
    PG_NOTIFY_TEMPLATE_RULEBOOK_DATA,
)
from aap_eda.api.exceptions import InvalidEventStreamRulebook
from aap_eda.api.serializers.decision_environment import (
    DecisionEnvironmentRefSerializer,
)
from aap_eda.api.serializers.eda_credential import EdaCredentialSerializer
from aap_eda.api.serializers.event_stream import EventStreamOutSerializer
from aap_eda.api.serializers.project import (
    ExtraVarRefSerializer,
    ProjectRefSerializer,
)
from aap_eda.api.serializers.rulebook import RulebookRefSerializer
from aap_eda.api.vault import encrypt_string
from aap_eda.core import models, validators
from aap_eda.core.enums import CredentialType, ProcessParentType
from aap_eda.core.utils.credentials import get_secret_fields
from aap_eda.core.utils.strings import (
    substitute_extra_vars,
    substitute_source_args,
    substitute_variables,
    swap_sources,
)

logger = logging.getLogger(__name__)


def _updated_ruleset(validated_data):
    try:
        sources_info = []

        for event_stream_id in validated_data["event_streams"]:
            event_stream = models.EventStream.objects.get(id=event_stream_id)

            if event_stream.rulebook:
                rulesets = yaml.safe_load(event_stream.rulebook.rulesets)
            else:
                rulesets = yaml.safe_load(PG_NOTIFY_TEMPLATE_RULEBOOK_DATA)

            extra_vars = rulesets[0]["sources"][0].get("extra_vars", {})
            encrypt_vars = rulesets[0]["sources"][0].get("encrypt_vars", [])

            password = ""
            if bool(encrypt_vars):
                password = secrets.token_urlsafe()

            extra_vars = substitute_extra_vars(
                event_stream.__dict__, extra_vars, encrypt_vars, password
            )

            source = rulesets[0]["sources"][0]["complementary_source"]
            source = substitute_source_args(
                event_stream.__dict__, source, extra_vars
            )
            sources_info.append(source)

        return swap_sources(validated_data["rulebook_rulesets"], sources_info)
    except Exception as e:
        logger.error(f"Failed to update rulesets: {e}")
        raise InvalidEventStreamRulebook(e)


def _handle_eda_credentials(
    validated_data: dict,
    extra_var_obj: models.ExtraVar,
    vault: models.CredentialType,
    password: str,
) -> bool:
    system_vault_credential_needed = False

    for eda_credential_id in validated_data["eda_credentials"]:
        eda_credential = models.EdaCredential.objects.get(id=eda_credential_id)
        if eda_credential.credential_type.id == vault.id:
            continue

        schema_inputs = eda_credential.credential_type.inputs
        injectors = eda_credential.credential_type.injectors
        secret_fields = get_secret_fields(schema_inputs)

        user_inputs = yaml.safe_load(eda_credential.inputs.get_secret_value())

        for key, value in user_inputs.items():
            if key in secret_fields:
                user_inputs[key] = encrypt_string(
                    password=password,
                    plaintext=value,
                    vault_id=EDA_SERVER_VAULT_LABEL,
                )
                system_vault_credential_needed = True

        data = substitute_variables(injectors, user_inputs)

        if extra_var_obj:
            existing_data = yaml.safe_load(extra_var_obj.extra_var)
            for key in data["extra_vars"]:
                existing_data[key] = data["extra_vars"][key]

            extra_var_obj.extra_var = yaml.dump(existing_data)
            extra_var_obj.save(update_fields=["extra_var"])
        else:
            extra_var = models.ExtraVar.objects.create(
                extra_var=yaml.dump(data["extra_vars"])
            )
            validated_data["extra_var_id"] = extra_var.id

    return system_vault_credential_needed


def _create_system_eda_credential(
    password: str, vault: models.CredentialType
) -> models.EdaCredential:
    inputs = {
        "vault_id": EDA_SERVER_VAULT_LABEL,
        "vault_password": password,
    }

    return models.EdaCredential.objects.create(
        name=f"{EDA_SERVER_VAULT_LABEL}-{uuid.uuid4()}",
        managed=True,
        inputs=json.dumps(inputs),
        credential_type=vault,
    )


def _get_vault_credential_type():
    return models.CredentialType.objects.get(name=CredentialType.VAULT)


class ActivationSerializer(serializers.ModelSerializer):
    """Serializer for the Activation model."""

    event_streams = serializers.ListField(
        required=False,
        allow_null=True,
        child=EventStreamOutSerializer(),
    )

    eda_credentials = serializers.ListField(
        required=False,
        allow_null=True,
        child=EdaCredentialSerializer(),
    )

    class Meta:
        model = models.Activation
        fields = [
            "id",
            "name",
            "description",
            "is_enabled",
            "status",
            "git_hash",
            "decision_environment_id",
            "project_id",
            "rulebook_id",
            "extra_var_id",
            "restart_completion_interval",
            "restart_failure_interval",
            "restart_failure_limit",
            "restart_policy",
            "restart_count",
            "rulebook_name",
            "ruleset_stats",
            "current_job_id",
            "created_at",
            "modified_at",
            "status_message",
            "awx_token_id",
            "event_streams",
            "eda_credentials",
            "log_level",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
            "rulebook_name",
        ]


class ActivationListSerializer(serializers.ModelSerializer):
    """Serializer for listing the Activation model objects."""

    rules_count = serializers.IntegerField()
    rules_fired_count = serializers.IntegerField()

    event_streams = serializers.ListField(
        required=False,
        allow_null=True,
        child=EventStreamOutSerializer(),
    )
    eda_credentials = serializers.ListField(
        required=False,
        allow_null=True,
        child=EdaCredentialSerializer(),
    )

    class Meta:
        model = models.Activation
        fields = [
            "id",
            "name",
            "description",
            "is_enabled",
            "status",
            "decision_environment_id",
            "project_id",
            "rulebook_id",
            "extra_var_id",
            "restart_completion_interval",
            "restart_failure_interval",
            "restart_failure_limit",
            "restart_policy",
            "restart_count",
            "rulebook_name",
            "current_job_id",
            "rules_count",
            "rules_fired_count",
            "created_at",
            "modified_at",
            "status_message",
            "awx_token_id",
            "event_streams",
            "log_level",
            "eda_credentials",
        ]
        read_only_fields = ["id", "created_at", "modified_at"]

    def to_representation(self, activation):
        rules_count, rules_fired_count = get_rules_count(
            activation.ruleset_stats
        )
        event_streams = [
            EventStreamOutSerializer(event_stream).data
            for event_stream in activation.event_streams.all()
        ]
        eda_credentials = [
            EdaCredentialSerializer(credential).data
            for credential in activation.eda_credentials.all()
        ]

        return {
            "id": activation.id,
            "name": activation.name,
            "description": activation.description,
            "is_enabled": activation.is_enabled,
            "status": activation.status,
            "decision_environment_id": activation.decision_environment_id,
            "project_id": activation.project_id,
            "rulebook_id": activation.rulebook_id,
            "extra_var_id": activation.extra_var_id,
            "restart_completion_interval": (
                activation.restart_completion_interval
            ),
            "restart_failure_interval": activation.restart_failure_interval,
            "restart_failure_limit": activation.restart_failure_limit,
            "restart_policy": activation.restart_policy,
            "restart_count": activation.restart_count,
            "rulebook_name": activation.rulebook_name,
            "current_job_id": activation.current_job_id,
            "rules_count": rules_count,
            "rules_fired_count": rules_fired_count,
            "created_at": activation.created_at,
            "modified_at": activation.modified_at,
            "status_message": activation.status_message,
            "awx_token_id": activation.awx_token_id,
            "event_streams": event_streams,
            "log_level": activation.log_level,
            "eda_credentials": eda_credentials,
        }


class ActivationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating the Activation."""

    class Meta:
        model = models.Activation
        fields = [
            "name",
            "description",
            "is_enabled",
            "decision_environment_id",
            "rulebook_id",
            "extra_var_id",
            "user",
            "restart_completion_interval",
            "restart_failure_interval",
            "restart_failure_limit",
            "restart_policy",
            "awx_token_id",
            "event_streams",
            "log_level",
            "eda_credentials",
        ]

    rulebook_id = serializers.IntegerField(
        validators=[validators.check_if_rulebook_exists]
    )
    extra_var_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        validators=[validators.check_if_extra_var_exists],
    )
    decision_environment_id = serializers.IntegerField(
        validators=[validators.check_if_de_exists]
    )
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    awx_token_id = serializers.IntegerField(
        allow_null=True,
        validators=[validators.check_if_awx_token_exists],
        required=False,
    )
    event_streams = serializers.ListField(
        required=False,
        allow_null=True,
        child=serializers.IntegerField(),
        validators=[validators.check_if_event_streams_exists],
    )
    eda_credentials = serializers.ListField(
        required=False,
        allow_null=True,
        child=serializers.IntegerField(),
    )

    def validate(self, data):
        user = data["user"]
        awx_token = models.AwxToken.objects.filter(
            id=data.get("awx_token_id"),
        ).first()
        if awx_token and awx_token.user != user:
            raise serializers.ValidationError(
                "The Awx Token does not belong to the user."
            )
        if not awx_token:
            validate_rulebook_token(data["rulebook_id"])

        if data.get("eda_credentials") and data.get("extra_var_id"):
            validate_eda_credentails(
                data.get("eda_credentials"), data.get("extra_var_id")
            )

        return data

    def create(self, validated_data):
        rulebook_id = validated_data["rulebook_id"]
        rulebook = models.Rulebook.objects.get(id=rulebook_id)
        validated_data["user_id"] = validated_data["user"].id
        validated_data["rulebook_name"] = rulebook.name
        validated_data["rulebook_rulesets"] = rulebook.rulesets
        validated_data["git_hash"] = rulebook.project.git_hash
        validated_data["project_id"] = rulebook.project.id
        if validated_data.get("event_streams"):
            validated_data["rulebook_rulesets"] = _updated_ruleset(
                validated_data
            )

        extra_var_obj = None
        password = secrets.token_urlsafe()
        system_vault_credential_needed = False

        if validated_data.get("extra_var_id"):
            extra_var_obj = models.ExtraVar.objects.get(
                id=validated_data["extra_var_id"]
            )

        vault = _get_vault_credential_type()

        if validated_data.get("eda_credentials"):
            system_vault_credential_needed = _handle_eda_credentials(
                validated_data, extra_var_obj, vault, password
            )

        if system_vault_credential_needed:
            validated_data[
                "eda_system_vault_credential"
            ] = _create_system_eda_credential(password, vault)

        return super().create(validated_data)


class ActivationInstanceSerializer(serializers.ModelSerializer):
    """Serializer for the Activation Instance model."""

    class Meta:
        model = models.RulebookProcess
        fields = [
            "id",
            "name",
            "status",
            "git_hash",
            "status_message",
            "activation_id",
            "event_stream_id",
            "started_at",
            "ended_at",
        ]
        read_only_fields = ["id", "started_at", "ended_at"]


class ActivationInstanceLogSerializer(serializers.ModelSerializer):
    """Serializer for the Activation Instance Log model."""

    class Meta:
        model = models.RulebookProcessLog
        fields = "__all__"
        read_only_fields = ["id"]


class ActivationReadSerializer(serializers.ModelSerializer):
    """Serializer for reading the Activation with related objects info."""

    decision_environment = DecisionEnvironmentRefSerializer(
        required=False, allow_null=True
    )
    project = ProjectRefSerializer(required=False, allow_null=True)
    rulebook = RulebookRefSerializer(required=False, allow_null=True)
    extra_var = ExtraVarRefSerializer(required=False, allow_null=True)
    instances = ActivationInstanceSerializer(many=True)
    rules_count = serializers.IntegerField()
    rules_fired_count = serializers.IntegerField()
    restarted_at = serializers.DateTimeField(required=False, allow_null=True)
    event_streams = serializers.ListField(
        required=False,
        allow_null=True,
        child=EventStreamOutSerializer(),
    )
    eda_credentials = serializers.ListField(
        required=False,
        allow_null=True,
        child=EdaCredentialSerializer(),
    )

    class Meta:
        model = models.Activation
        fields = [
            "id",
            "name",
            "description",
            "is_enabled",
            "decision_environment",
            "status",
            "git_hash",
            "project",
            "rulebook",
            "extra_var",
            "instances",
            "restart_completion_interval",
            "restart_failure_interval",
            "restart_failure_limit",
            "restart_policy",
            "restart_count",
            "rulebook_name",
            "current_job_id",
            "rules_count",
            "rules_fired_count",
            "created_at",
            "modified_at",
            "restarted_at",
            "status_message",
            "awx_token_id",
            "eda_credentials",
            "event_streams",
            "log_level",
        ]
        read_only_fields = ["id", "created_at", "modified_at", "restarted_at"]

    def to_representation(self, activation):
        decision_environment = (
            DecisionEnvironmentRefSerializer(
                activation.decision_environment
            ).data
            if activation.decision_environment
            else None
        )
        project = (
            ProjectRefSerializer(activation.project).data
            if activation.project
            else None
        )
        rulebook = (
            RulebookRefSerializer(activation.rulebook).data
            if activation.rulebook
            else None
        )
        extra_var = (
            ExtraVarRefSerializer(activation.extra_var).data
            if activation.extra_var
            else None
        )
        activation_instances = models.RulebookProcess.objects.filter(
            activation_id=activation.id,
            parent_type=ProcessParentType.ACTIVATION,
        )
        rules_count, rules_fired_count = get_rules_count(
            activation.ruleset_stats
        )
        # restart_count can be zero even if there are more than one instance
        # because it is incremented only when the activation
        # is restarted automatically
        restarted_at = (
            activation_instances.latest("started_at").started_at
            if len(activation_instances) > 1 and activation.restart_count > 0
            else None
        )

        event_streams = [
            EventStreamOutSerializer(event_stream).data
            for event_stream in activation.event_streams.all()
        ]
        eda_credentials = [
            EdaCredentialSerializer(credential).data
            for credential in activation.eda_credentials.all()
        ]

        return {
            "id": activation.id,
            "name": activation.name,
            "description": activation.description,
            "is_enabled": activation.is_enabled,
            "decision_environment": decision_environment,
            "status": activation.status,
            "git_hash": activation.git_hash,
            "project": project,
            "rulebook": rulebook,
            "extra_var": extra_var,
            "instances": ActivationInstanceSerializer(
                activation_instances, many=True
            ).data,
            "restart_completion_interval": (
                activation.restart_completion_interval
            ),
            "restart_failure_interval": activation.restart_failure_interval,
            "restart_failure_limit": activation.restart_failure_limit,
            "restart_policy": activation.restart_policy,
            "restart_count": activation.restart_count,
            "rulebook_name": activation.rulebook_name,
            "current_job_id": activation.current_job_id,
            "rules_count": rules_count,
            "rules_fired_count": rules_fired_count,
            "created_at": activation.created_at,
            "modified_at": activation.modified_at,
            "restarted_at": restarted_at,
            "status_message": activation.status_message,
            "awx_token_id": activation.awx_token_id,
            "event_streams": event_streams,
            "log_level": activation.log_level,
            "eda_credentials": eda_credentials,
        }


class PostActivationSerializer(serializers.ModelSerializer):
    """Serializer for validating activations before reactivate them."""

    name = serializers.CharField(required=True)
    decision_environment_id = serializers.IntegerField(
        validators=[validators.check_if_de_exists]
    )
    extra_var_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        validators=[validators.check_if_extra_var_exists],
    )
    # TODO: is_activation_valid needs to tell event stream/activation
    awx_token_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        validators=[validators.check_if_awx_token_exists],
    )
    rulebook_id = serializers.IntegerField(allow_null=True)

    def validate(self, data):
        awx_token = data.get("awx_token_id")

        if not awx_token:
            validate_rulebook_token(data["rulebook_id"])

        return data

    class Meta:
        model = models.Activation
        fields = [
            "id",
            "name",
            "status",
            "decision_environment_id",
            "extra_var_id",
            "user_id",
            "created_at",
            "modified_at",
            "awx_token_id",
            "rulebook_id",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
        ]


def get_rules_count(ruleset_stats: dict) -> tuple[int, int]:
    rules_count = 0
    rules_fired_count = 0

    # TODO: add schema for validating ruleset_stats
    for ruleset_stat in ruleset_stats.values():
        rules_count += ruleset_stat.get("numberOfRules", 0)
        rules_fired_count += ruleset_stat.get("rulesTriggered", 0)

    return rules_count, rules_fired_count


def is_activation_valid(activation: models.Activation) -> tuple[bool, str]:
    serializer = PostActivationSerializer(data=activation.__dict__)

    valid = serializer.is_valid()
    message = parse_validation_errors(serializer.errors)

    return valid, message


def parse_validation_errors(errors: dict) -> str:
    messages = {key: str(error[0]) for key, error in errors.items() if error}

    return str(messages)


def validate_rulebook_token(rulebook_id: Union[int, None]) -> None:
    """Validate if the rulebook requires an Awx Token."""
    if rulebook_id is None:
        return

    rulebook = models.Rulebook.objects.get(id=rulebook_id)

    # TODO: rulesets are stored as a string in the rulebook model
    # proper instrospection should require a validation of the
    # rulesets. https://issues.redhat.com/browse/AAP-19202
    try:
        rulesets_data = rulebook.get_rulesets_data()
    except ValueError:
        raise serializers.ValidationError("Invalid rulebook data.")

    if validators.check_rulesets_require_token(
        rulesets_data,
    ):
        raise serializers.ValidationError(
            "The rulebook requires an Awx Token.",
        )


def validate_eda_credentails(
    eda_credential_ids: list[int], extra_var_id: int
) -> None:
    try:
        vault = _get_vault_credential_type()
        extra_var = models.ExtraVar.objects.get(id=extra_var_id)
        existing_data = yaml.safe_load(extra_var.extra_var)
    except models.CredentialType.DoesNotExist:
        raise serializers.ValidationError(
            f"CredentialType with name '{CredentialType.VAULT}' does not exist"
        )
    except models.ExtraVar.DoesNotExist:
        raise serializers.ValidationError(
            f"ExtraVar with id {extra_var_id} does not exist"
        )

    existing_keys = [*existing_data.keys()]

    for eda_credential_id in eda_credential_ids:
        try:
            eda_credential = models.EdaCredential.objects.get(
                id=eda_credential_id
            )

            if eda_credential.credential_type.id == vault.id:
                continue

            injectors = eda_credential.credential_type.injectors

            for key in injectors["extra_vars"]:
                if key in existing_keys or key in existing_data:
                    message = (
                        f"Key: {key} already exists in extra var. "
                        f"It conflicts with credential type: "
                        f"{eda_credential.credential_type.name}. "
                        f"Please check injectors."
                    )
                    raise serializers.ValidationError(message)

                existing_keys.append(key)
        except models.EdaCredential.DoesNotExist:
            raise serializers.ValidationError(
                f"EdaCredential with id {eda_credential_id} does not exist"
            )
