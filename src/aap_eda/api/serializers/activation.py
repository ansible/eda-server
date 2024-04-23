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
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

import yaml
from django.conf import settings
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
from aap_eda.api.serializers.organization import OrganizationRefSerializer
from aap_eda.api.serializers.project import (
    ANSIBLE_VAULT_STRING,
    ENCRYPTED_STRING,
    ProjectRefSerializer,
)
from aap_eda.api.serializers.rulebook import RulebookRefSerializer
from aap_eda.api.vault import encrypt_string
from aap_eda.core import models, validators
from aap_eda.core.enums import DefaultCredentialType, ProcessParentType
from aap_eda.core.utils.credentials import get_secret_fields
from aap_eda.core.utils.k8s_service_name import (
    InvalidRFC1035LabelError,
    create_k8s_service_name,
)
from aap_eda.core.utils.strings import (
    substitute_extra_vars,
    substitute_source_args,
    substitute_variables,
    swap_sources,
)

logger = logging.getLogger(__name__)


@dataclass
class VaultData:
    password: str = secrets.token_urlsafe()
    password_used: bool = False


def _updated_ruleset(validated_data: dict, vault_data: VaultData):
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

            if bool(encrypt_vars):
                vault_data.password_used = True

            extra_vars = substitute_extra_vars(
                event_stream.__dict__,
                extra_vars,
                encrypt_vars,
                vault_data.password,
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


def _update_k8s_service_name(validated_data: dict) -> str:
    service_name = validated_data.get("k8s_service_name")
    return service_name or create_k8s_service_name(validated_data["name"])


def _extend_extra_vars_from_credentials(
    validated_data: dict, credential_data: Union[str, int, Dict, List]
) -> Union[str, int, Dict, List]:
    if validated_data.get("extra_var"):
        updated_extra_vars = yaml.safe_load(validated_data.get("extra_var"))
        for key in credential_data.get("extra_vars", []):
            updated_extra_vars[key] = credential_data["extra_vars"][key]
        return updated_extra_vars
    else:
        return yaml.dump(credential_data["extra_vars"])


def _update_extra_vars_from_eda_credentials(
    validated_data: dict,
    vault_data: VaultData,
    creating: bool,
    activation: models.Activation = None,
) -> None:
    for eda_credential_id in validated_data["eda_credentials"]:
        eda_credential = models.EdaCredential.objects.get(id=eda_credential_id)
        if eda_credential.credential_type.name in [
            DefaultCredentialType.VAULT,
            DefaultCredentialType.AAP,
        ]:
            continue

        schema_inputs = eda_credential.credential_type.inputs
        injectors = eda_credential.credential_type.injectors
        secret_fields = get_secret_fields(schema_inputs)

        user_inputs = yaml.safe_load(eda_credential.inputs.get_secret_value())

        if any(key in user_inputs for key in secret_fields):
            if creating:
                vault_data.password_used = True

        for key, value in user_inputs.items():
            if key in secret_fields:
                user_inputs[key] = encrypt_string(
                    password=vault_data.password,
                    plaintext=value,
                    vault_id=EDA_SERVER_VAULT_LABEL,
                )

        data = substitute_variables(injectors, user_inputs)

        updated_extra_vars = _extend_extra_vars_from_credentials(
            validated_data, data
        )
        # when creating an activation we need to return the updated extra vars
        if creating:
            return updated_extra_vars
        # if not creating, update the existing activation object extra vars
        else:
            activation.extra_var = yaml.dump(updated_extra_vars)
            activation.save(update_fields=["extra_var"])


def _create_system_eda_credential(
    password: str, vault: models.CredentialType, organization_id: Optional[int]
) -> models.EdaCredential:
    inputs = {
        "vault_id": EDA_SERVER_VAULT_LABEL,
        "vault_password": password,
    }

    kwargs = {
        "name": f"{EDA_SERVER_VAULT_LABEL}-{uuid.uuid4()}",
        "managed": True,
        "inputs": json.dumps(inputs),
        "credential_type": vault,
    }
    if organization_id:
        kwargs["organization_id"] = organization_id

    return models.EdaCredential.objects.create(**kwargs)


def _get_vault_credential_type():
    return models.CredentialType.objects.get(name=DefaultCredentialType.VAULT)


def replace_vault_data(extra_var):
    data = {
        key: (
            ENCRYPTED_STRING
            if isinstance(value, str) and ANSIBLE_VAULT_STRING in value
            else value
        )
        for key, value in yaml.safe_load(extra_var).items()
    }

    return yaml.safe_dump(data).rstrip("\n")


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
            "extra_var",
            "decision_environment_id",
            "project_id",
            "rulebook_id",
            "organization_id",
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
    k8s_service_name = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Service name of the activation",
    )

    class Meta:
        model = models.Activation
        fields = [
            "id",
            "name",
            "description",
            "is_enabled",
            "status",
            "extra_var",
            "decision_environment_id",
            "project_id",
            "rulebook_id",
            "organization_id",
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
            "k8s_service_name",
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
        extra_var = (
            replace_vault_data(activation.extra_var)
            if activation.extra_var
            else None
        )

        return {
            "id": activation.id,
            "name": activation.name,
            "description": activation.description,
            "is_enabled": activation.is_enabled,
            "status": activation.status,
            "decision_environment_id": activation.decision_environment_id,
            "project_id": activation.project_id,
            "rulebook_id": activation.rulebook_id,
            "extra_var": extra_var,
            "organization_id": activation.organization_id,
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
            "k8s_service_name": activation.k8s_service_name,
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
            "extra_var",
            "organization_id",
            "user",
            "restart_policy",
            "awx_token_id",
            "event_streams",
            "log_level",
            "eda_credentials",
            "k8s_service_name",
        ]

    organization_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        validators=[validators.check_if_organization_exists],
    )
    rulebook_id = serializers.IntegerField(
        validators=[validators.check_if_rulebook_exists]
    )
    extra_var = serializers.CharField(
        required=False,
        allow_null=True,
        validators=[validators.is_extra_var_dict],
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
    k8s_service_name = serializers.CharField(
        required=False,
        allow_null=True,
        validators=[validators.check_if_rfc_1035_compliant],
    )

    def validate(self, data):
        _validate_credentials_and_token_and_rulebook(data=data, creating=True)

        return data

    def create(self, validated_data):
        rulebook_id = validated_data["rulebook_id"]
        rulebook = models.Rulebook.objects.get(id=rulebook_id)
        validated_data["user_id"] = validated_data["user"].id
        validated_data["rulebook_name"] = rulebook.name
        validated_data["rulebook_rulesets"] = rulebook.rulesets
        validated_data["git_hash"] = rulebook.project.git_hash
        validated_data["project_id"] = rulebook.project.id

        if settings.DEPLOYMENT_TYPE == "k8s":
            validated_data["k8s_service_name"] = _update_k8s_service_name(
                validated_data
            )

        vault_data = VaultData()

        if validated_data.get("event_streams"):
            validated_data["rulebook_rulesets"] = _updated_ruleset(
                validated_data, vault_data
            )

        vault = _get_vault_credential_type()

        if validated_data.get("eda_credentials"):
            validated_data[
                "extra_var"
            ] = _update_extra_vars_from_eda_credentials(
                validated_data=validated_data,
                vault_data=vault_data,
                creating=True,
            )

        if vault_data.password_used:
            validated_data[
                "eda_system_vault_credential"
            ] = _create_system_eda_credential(
                vault_data.password,
                vault,
                validated_data.get("organization_id"),
            )

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
            "organization_id",
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
    instances = ActivationInstanceSerializer(many=True)
    organization = OrganizationRefSerializer()
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
    k8s_service_name = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Service name of the activation",
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
            "organization",
            "instances",
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
            "k8s_service_name",
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
        organization = (
            OrganizationRefSerializer(activation.organization).data
            if activation.organization
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
        extra_var = (
            replace_vault_data(activation.extra_var)
            if activation.extra_var
            else None
        )

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
            "organization": organization,
            "instances": ActivationInstanceSerializer(
                activation_instances, many=True
            ).data,
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
            "k8s_service_name": activation.k8s_service_name,
        }


class PostActivationSerializer(serializers.ModelSerializer):
    """Serializer for validating activations before reactivate them."""

    id = serializers.IntegerField(
        required=False,
        allow_null=True,
    )
    name = serializers.CharField(required=True)
    decision_environment_id = serializers.IntegerField(
        validators=[validators.check_if_de_exists]
    )
    # TODO: is_activation_valid needs to tell event stream/activation
    awx_token_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        validators=[validators.check_if_awx_token_exists],
    )
    rulebook_id = serializers.IntegerField(allow_null=True)
    eda_credentials = serializers.ListField(
        required=False,
        allow_null=True,
        child=serializers.IntegerField(),
    )
    k8s_service_name = serializers.CharField(
        required=False,
        allow_null=True,
        validators=[validators.check_if_rfc_1035_compliant],
    )

    def validate(self, data):
        _validate_credentials_and_token_and_rulebook(data=data, creating=False)

        return data

    class Meta:
        model = models.Activation
        fields = [
            "id",
            "name",
            "status",
            "extra_var",
            "decision_environment_id",
            "organization_id",
            "user_id",
            "created_at",
            "modified_at",
            "awx_token_id",
            "rulebook_id",
            "eda_credentials",
            "k8s_service_name",
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
    data = activation.__dict__
    data["eda_credentials"] = [
        obj.id for obj in activation.eda_credentials.all()
    ]
    serializer = PostActivationSerializer(data=data)

    valid = serializer.is_valid()
    message = parse_validation_errors(serializer.errors)

    return valid, message


def parse_validation_errors(errors: dict) -> str:
    messages = {key: str(error[0]) for key, error in errors.items() if error}

    return str(messages)


def _validate_credentials_and_token_and_rulebook(
    data: dict, creating: bool
) -> None:
    """Validate Awx Token and AAP credentials."""
    eda_credentials = data.get("eda_credentials", [])
    aap_credentials = _get_aap_credentials_if_exists(eda_credentials)

    # validate EDA credentials
    if creating:
        _validate_eda_credentials(data)
    else:
        # update extra vars if needs
        activation = models.Activation.objects.get(id=data["id"])
        vault_credential = activation.eda_system_vault_credential
        if vault_credential:
            inputs = yaml.safe_load(vault_credential.inputs.get_secret_value())
            vault_data = VaultData(password=inputs["vault_password"])
        else:
            vault_data = VaultData()

        _update_extra_vars_from_eda_credentials(
            validated_data=data,
            vault_data=vault_data,
            creating=False,
            activation=activation,
        )

    # validate AAP credentials
    if aap_credentials:
        for credential in aap_credentials:
            _validate_aap_credential(credential)

        return

    # validate awx token
    awx_token = _validate_awx_token(data)

    # validate rulebook
    _validate_rulebook(data, awx_token is not None)

    # validate if activation name is compatible with RFC 1035
    if not data.get("k8s_service_name") and settings.DEPLOYMENT_TYPE == "k8s":
        try:
            create_k8s_service_name(data["name"])
        except InvalidRFC1035LabelError as e:
            raise serializers.ValidationError({"k8s_service_name": [str(e)]})


def _validate_awx_token(data: dict) -> models.AwxToken:
    """Validate Awx Token, return it if it's valid."""
    awx_token_id = data.get("awx_token_id")

    if awx_token_id is None:
        return

    user = data.get("user")
    awx_token = models.AwxToken.objects.filter(id=awx_token_id).first()
    if awx_token and user and awx_token.user != user:
        raise serializers.ValidationError(
            "The Awx Token does not belong to the user."
        )

    return awx_token


def _validate_rulebook(data: dict, with_token: bool = False) -> None:
    rulebook_id = data.get("rulebook_id")
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

    if not with_token and validators.check_rulesets_require_token(
        rulesets_data,
    ):
        raise serializers.ValidationError(
            "The rulebook requires an Awx Token or RH AAP credential.",
        )


def _validate_aap_credential(credential: models.EdaCredential) -> None:
    inputs = yaml.safe_load(credential.inputs.get_secret_value())

    username = inputs.get("username")
    password = inputs.get("password")
    token = inputs.get("oauth_token")

    if not username and not password and not token:
        raise serializers.ValidationError(
            "Invalid RH AAP credential: "
            "either username/password or token has to be set"
        )

    if not token and (not username or not password):
        raise serializers.ValidationError(
            "Invalid RH AAP credential: "
            "both username and password have to be set when token is empty"
        )


def _validate_eda_credentials(data: dict) -> None:
    eda_credential_ids = data.get("eda_credentials")
    if eda_credential_ids is None:
        return

    existing_keys = []
    extra_var = data.get("extra_var")

    try:
        vault = _get_vault_credential_type()
        if extra_var:
            existing_data = yaml.safe_load(extra_var)
            existing_keys = [*existing_data.keys()]
    except models.CredentialType.DoesNotExist:
        raise serializers.ValidationError(
            f"CredentialType with name '{DefaultCredentialType.VAULT}'"
            " does not exist"
        )

    for eda_credential_id in eda_credential_ids:
        try:
            eda_credential = models.EdaCredential.objects.get(
                id=eda_credential_id
            )

            if eda_credential.credential_type.id == vault.id:
                continue

            injectors = eda_credential.credential_type.injectors

            for key in injectors.get("extra_vars", []):
                if key in existing_keys:
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


def _get_aap_credentials_if_exists(
    eda_credential_ids: list[int],
) -> list[models.EdaCredential]:
    aap_credential_type = models.CredentialType.objects.get(
        name=DefaultCredentialType.AAP
    )
    eda_credentials = [
        models.EdaCredential.objects.get(pk=eda_credential_id)
        for eda_credential_id in eda_credential_ids
    ]

    return [
        eda_credential
        for eda_credential in eda_credentials
        if eda_credential.credential_type.id == aap_credential_type.id
    ]
