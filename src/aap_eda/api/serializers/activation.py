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
from typing import Optional

import yaml
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from aap_eda.api.constants import (
    EDA_SERVER_VAULT_LABEL,
    SOURCE_MAPPING_ERROR_KEY,
)
from aap_eda.api.exceptions import InvalidEventStreamSource
from aap_eda.api.serializers.decision_environment import (
    DecisionEnvironmentRefSerializer,
)
from aap_eda.api.serializers.eda_credential import EdaCredentialSerializer
from aap_eda.api.serializers.event_stream import EventStreamOutSerializer
from aap_eda.api.serializers.fields.basic_user import BasicUserFieldSerializer
from aap_eda.api.serializers.fields.yaml import YAMLSerializerField
from aap_eda.api.serializers.organization import OrganizationRefSerializer
from aap_eda.api.serializers.project import (
    ANSIBLE_VAULT_STRING,
    ENCRYPTED_STRING,
    ProjectRefSerializer,
)
from aap_eda.api.serializers.rulebook import RulebookRefSerializer
from aap_eda.api.serializers.user import BasicUserSerializer
from aap_eda.api.vault import encrypt_string
from aap_eda.core import models, validators
from aap_eda.core.enums import DefaultCredentialType, ProcessParentType
from aap_eda.core.exceptions import ParseError
from aap_eda.core.utils.credentials import get_secret_fields
from aap_eda.core.utils.k8s_service_name import create_k8s_service_name
from aap_eda.core.utils.rulebook import (
    build_source_list,
    get_rulebook_hash,
    swap_event_stream_sources,
)
from aap_eda.core.utils.strings import substitute_variables

logger = logging.getLogger(__name__)
REQUIRED_KEYS = [
    "event_stream_id",
    "event_stream_name",
    "source_name",
    "rulebook_hash",
]

PG_NOTIFY_DSN = (
    "host={{postgres_db_host}} port={{postgres_db_port}} "
    "dbname={{postgres_db_name}} user={{postgres_db_user}} "
    "password={{postgres_db_password}} sslmode={{postgres_sslmode}} "
    "sslcert={{eda.filename.postgres_sslcert|default(None)}} "
    "sslkey={{eda.filename.postgres_sslkey|default(None)}} "
    "sslpassword={{postgres_sslpassword|default(None)}} "
    "sslrootcert={{eda.filename.postgres_sslrootcert|default(None)}}"
)


@dataclass
class VaultData:
    password: str = secrets.token_urlsafe()
    password_used: bool = False


def _update_event_stream_source(validated_data: dict) -> str:
    try:
        source_mappings = yaml.safe_load(validated_data["source_mappings"])
        sources_info = {}
        for source_map in source_mappings:
            event_stream_id = source_map.get("event_stream_id")
            obj = models.EventStream.objects.get(id=event_stream_id)

            sources_info[obj.name] = {
                "ansible.eda.pg_listener": {
                    "dsn": PG_NOTIFY_DSN,
                    "channels": [obj.channel_name],
                },
            }

        return swap_event_stream_sources(
            validated_data["rulebook_rulesets"], sources_info, source_mappings
        )
        # TODO: Can we catch a better exception
    except Exception as e:
        logger.error(
            "Failed to update event stream source in rulesets: %s", str(e)
        )
        raise InvalidEventStreamSource(e) from e


def _update_k8s_service_name(validated_data: dict) -> str:
    service_name = validated_data.get("k8s_service_name")
    return service_name or create_k8s_service_name(validated_data["name"])


def _extend_extra_vars_from_credentials(
    validated_data: dict, extra_vars: dict
) -> str:
    if validated_data.get("extra_var"):
        updated_extra_vars = yaml.safe_load(validated_data.get("extra_var"))
        for key, value in extra_vars.items():
            updated_extra_vars[key] = value
        return yaml.dump(updated_extra_vars)
    else:
        return yaml.dump(extra_vars)


def _update_extra_vars_from_eda_credentials(
    validated_data: dict,
    vault_data: VaultData,
    creating: bool,
    activation: models.Activation = None,
) -> None:
    for eda_credential_id in validated_data["eda_credentials"]:
        eda_credential = models.EdaCredential.objects.get(id=eda_credential_id)
        if (
            creating
            and eda_credential.credential_type.name
            == DefaultCredentialType.AAP
        ):
            vault_data.password_used = True
        if eda_credential.credential_type.name in [
            DefaultCredentialType.VAULT,
            DefaultCredentialType.AAP,
        ]:
            continue

        schema_inputs = eda_credential.credential_type.inputs
        injectors = eda_credential.credential_type.injectors
        secret_fields = get_secret_fields(schema_inputs)

        user_inputs = yaml.safe_load(eda_credential.inputs.get_secret_value())

        if creating and any(key in user_inputs for key in secret_fields):
            vault_data.password_used = True

        if not injectors or "extra_vars" not in injectors:
            continue

        for key, value in user_inputs.items():
            if key in secret_fields and value is not None:
                logger.info("Encrypting secret field %s", key)
                user_inputs[key] = encrypt_string(
                    password=vault_data.password,
                    plaintext=value,
                    vault_id=EDA_SERVER_VAULT_LABEL,
                )

        injected_extra_vars = substitute_variables(
            injectors["extra_vars"], user_inputs
        )

        updated_extra_vars = _extend_extra_vars_from_credentials(
            validated_data, injected_extra_vars
        )
        # when creating an activation we need to return the updated extra vars
        if creating:
            validated_data["extra_var"] = updated_extra_vars
        # if not creating, update the existing activation object extra vars
        else:
            activation.extra_var = updated_extra_vars
            activation.save(update_fields=["extra_var"])


def _get_user_extra_vars(
    activation: models.Activation, extra_var_str: str
) -> str:
    if not extra_var_str:
        return ""
    extra_vars = yaml.safe_load(extra_var_str)

    # remove extra_vars injected from credentials
    for eda_credential in activation.eda_credentials.all():
        injectors = eda_credential.credential_type.injectors
        if not injectors or "extra_vars" not in injectors:
            continue

        for key, _value in injectors["extra_vars"].items():
            extra_vars.pop(key, None)
    return yaml.dump(extra_vars)


def _update_event_streams_and_credential(validated_data: dict):
    validated_data["rulebook_rulesets"] = _update_event_stream_source(
        validated_data
    )
    eda_credentials = validated_data.get("eda_credentials", [])
    postgres_cred = models.EdaCredential.objects.filter(
        name=settings.DEFAULT_SYSTEM_PG_NOTIFY_CREDENTIAL_NAME
    ).first()
    if postgres_cred.id not in eda_credentials:
        eda_credentials.append(postgres_cred.id)
    validated_data["eda_credentials"] = eda_credentials


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

    return yaml.safe_dump(data)


class ActivationSerializer(serializers.ModelSerializer):
    """Serializer for the Activation model."""

    eda_credentials = serializers.ListField(
        required=False,
        allow_null=True,
        child=EdaCredentialSerializer(),
    )

    event_streams = serializers.ListField(
        required=False,
        allow_null=True,
        child=EventStreamOutSerializer(),
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
            "edited_at",
            "status_message",
            "awx_token_id",
            "eda_credentials",
            "log_level",
            "event_streams",
            "skip_audit_events",
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

    eda_credentials = serializers.ListField(
        required=False,
        allow_null=True,
        child=EdaCredentialSerializer(),
    )
    k8s_service_name = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Service name of the activation",
    )
    event_streams = serializers.ListField(
        required=False,
        allow_null=True,
        child=EventStreamOutSerializer(),
    )
    created_by = BasicUserFieldSerializer()
    modified_by = BasicUserFieldSerializer()
    edited_by = BasicUserFieldSerializer()

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
            "edited_at",
            "created_by",
            "modified_by",
            "edited_by",
            "status_message",
            "awx_token_id",
            "log_level",
            "eda_credentials",
            "k8s_service_name",
            "event_streams",
            "source_mappings",
            "skip_audit_events",
            "log_tracking_id",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
            "log_tracking_id",
        ]

    def to_representation(self, activation):
        rules_count, rules_fired_count = get_rules_count(
            activation.ruleset_stats
        )
        eda_credentials = [
            EdaCredentialSerializer(credential).data
            for credential in activation.eda_credentials.filter(managed=False)
        ]
        extra_var = (
            replace_vault_data(activation.extra_var)
            if activation.extra_var
            else None
        )
        event_streams = [
            EventStreamOutSerializer(event_stream).data
            for event_stream in activation.event_streams.all()
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
            "edited_at": activation.edited_at,
            "status_message": activation.status_message,
            "awx_token_id": activation.awx_token_id,
            "log_level": activation.log_level,
            "eda_credentials": eda_credentials,
            "k8s_service_name": activation.k8s_service_name,
            "event_streams": event_streams,
            "source_mappings": activation.source_mappings,
            "skip_audit_events": activation.skip_audit_events,
            "log_tracking_id": activation.log_tracking_id,
            "created_by": BasicUserSerializer(activation.created_by).data,
            "modified_by": BasicUserSerializer(activation.modified_by).data,
            "edited_by": BasicUserSerializer(activation.edited_by).data,
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
            "log_level",
            "eda_credentials",
            "k8s_service_name",
            "source_mappings",
            "skip_audit_events",
        ]

    organization_id = serializers.IntegerField(
        required=True,
        allow_null=False,
        validators=[validators.check_if_organization_exists],
        error_messages={
            "null": "Organization is needed",
            "required": "Organization is required",
        },
    )
    rulebook_id = serializers.IntegerField(
        validators=[validators.check_if_rulebook_exists],
        error_messages={
            "null": "Rulebook is needed",
            "required": "Rulebook is required",
        },
    )
    extra_var = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        validators=[validators.is_extra_var_dict],
    )
    decision_environment_id = serializers.IntegerField(
        validators=[validators.check_if_de_exists],
        error_messages={
            "null": "Decision Environment is needed",
            "required": "Decision Environment is required",
        },
    )
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    awx_token_id = serializers.IntegerField(
        allow_null=True,
        validators=[validators.check_if_awx_token_exists],
        required=False,
    )
    eda_credentials = serializers.ListField(
        required=False,
        allow_null=False,
        child=serializers.IntegerField(),
        validators=[
            validators.check_multiple_credentials,
            validators.check_single_aap_credential,
        ],
    )
    k8s_service_name = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        validators=[validators.check_if_rfc_1035_compliant],
    )

    def validate(self, data):
        _validate_credentials_and_token_and_rulebook(data=data, creating=True)
        _validate_sources_with_event_streams(data=data)
        return data

    def create(self, validated_data):
        rulebook_id = validated_data["rulebook_id"]
        rulebook = models.Rulebook.objects.get(id=rulebook_id)
        validated_data["user_id"] = validated_data["user"].id
        validated_data["rulebook_name"] = rulebook.name
        validated_data["rulebook_rulesets"] = rulebook.rulesets
        validated_data["git_hash"] = rulebook.project.git_hash
        validated_data["project_id"] = rulebook.project.id
        validated_data["log_tracking_id"] = str(uuid.uuid4())

        if settings.DEPLOYMENT_TYPE == "k8s":
            validated_data["k8s_service_name"] = _update_k8s_service_name(
                validated_data
            )

        vault_data = VaultData()

        if validated_data.get("source_mappings", []):
            _update_event_streams_and_credential(validated_data)

        if validated_data.get("eda_credentials"):
            _update_extra_vars_from_eda_credentials(
                validated_data=validated_data,
                vault_data=vault_data,
                creating=True,
            )

        if vault_data.password_used:
            validated_data[
                "eda_system_vault_credential"
            ] = _create_system_eda_credential(
                vault_data.password,
                _get_vault_credential_type(),
                validated_data.get("organization_id"),
            )

        return super().create(validated_data)


class ActivationCopySerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True, validators=[validators.check_if_activation_name_used]
    )

    class Meta:
        model = models.Activation
        fields = ["name"]

    def copy(self) -> dict:
        activation: models.Activation = self.instance
        copied_data = {
            "name": self.validated_data["name"],
            "description": activation.description,
            "is_enabled": False,
            "decision_environment": activation.decision_environment,
            "rulebook": activation.rulebook,
            "extra_var": activation.extra_var,
            "organization": activation.organization,
            "user": activation.user,
            "restart_policy": activation.restart_policy,
            "awx_token_id": activation.awx_token,
            "log_level": activation.log_level,
            "eda_credentials": activation.eda_credentials.all(),
            "k8s_service_name": activation.k8s_service_name,
            "source_mappings": activation.source_mappings,
            "event_streams": activation.event_streams.all(),
            "skip_audit_events": activation.skip_audit_events,
            "rulebook_name": activation.rulebook.name,
            "rulebook_rulesets": activation.rulebook_rulesets,
            "git_hash": activation.rulebook.project.git_hash,
            "project": activation.rulebook.project,
            "log_tracking_id": str(uuid.uuid4()),
        }
        if activation.eda_system_vault_credential:
            inputs = yaml.safe_load(
                activation.eda_system_vault_credential.inputs.get_secret_value()  # noqa E501
            )
            copied_data[
                "eda_system_vault_credential"
            ] = _create_system_eda_credential(
                inputs["vault_password"],
                _get_vault_credential_type(),
                activation.organization.id,
            )

        return super().create(copied_data)


class ActivationUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating the Activation."""

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
            "log_level",
            "eda_credentials",
            "k8s_service_name",
            "source_mappings",
            "skip_audit_events",
        ]

    organization_id = serializers.IntegerField(
        required=False,
        allow_null=False,
        validators=[validators.check_if_organization_exists],
        error_messages={"null": "Organization is needed"},
    )
    rulebook_id = serializers.IntegerField(
        validators=[validators.check_if_rulebook_exists],
        error_messages={"null": "Rulebook is needed"},
    )
    extra_var = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        validators=[validators.is_extra_var_dict],
    )
    decision_environment_id = serializers.IntegerField(
        validators=[validators.check_if_de_exists],
        error_messages={"null": "Decision Environment is needed"},
    )
    awx_token_id = serializers.IntegerField(
        allow_null=True,
        validators=[validators.check_if_awx_token_exists],
        required=False,
    )
    eda_credentials = serializers.ListField(
        required=False,
        allow_null=False,
        child=serializers.IntegerField(),
        validators=[
            validators.check_multiple_credentials,
            validators.check_single_aap_credential,
        ],
    )
    k8s_service_name = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        validators=[validators.check_if_rfc_1035_compliant],
    )

    def refill_needed_data(
        self, data: dict, activation: models.Activation
    ) -> None:
        if "name" not in data:
            data["name"] = activation.name
        if "k8s_service_name" not in data:
            data["k8s_service_name"] = activation.k8s_service_name
        if "extra_var" not in data:
            data["extra_var"] = activation.extra_var
        data["extra_var"] = _get_user_extra_vars(activation, data["extra_var"])
        if "eda_credentials" not in data:
            data["eda_credentials"] = [
                cred.id
                for cred in activation.eda_credentials.filter(managed=False)
            ]
        if "source_mappings" not in data:
            data["source_mappings"] = activation.source_mappings

    def validate(self, data):
        _validate_credentials_and_token_and_rulebook(data=data, creating=True)
        _validate_sources_with_event_streams(data=data)
        return data

    def prepare_update(self, activation: models.Activation):
        rulebook_id = self.validated_data.get("rulebook_id")
        self.validated_data["user_id"] = self.context["request"].user.id
        self.validated_data["edited_at"] = timezone.now()
        self.validated_data["edited_by"] = self.context["request"].user
        if settings.DEPLOYMENT_TYPE == "k8s":
            self.validated_data["k8s_service_name"] = _update_k8s_service_name(
                self.validated_data
            )
        if rulebook_id:
            rulebook = models.Rulebook.objects.get(id=rulebook_id)
            self.validated_data["rulebook_name"] = rulebook.name
            self.validated_data["rulebook_rulesets"] = rulebook.rulesets
            self.validated_data["git_hash"] = rulebook.project.git_hash
            self.validated_data["project_id"] = rulebook.project.id

        system_vault_credential = activation.eda_system_vault_credential
        if system_vault_credential:
            inputs = yaml.safe_load(
                system_vault_credential.inputs.get_secret_value()
            )
            vault_data = VaultData(inputs["vault_password"], True)
        else:
            vault_data = VaultData()
        if yaml.safe_load(self.validated_data.get("source_mappings", "")):
            if not rulebook_id:
                # load the original ruleset
                self.validated_data[
                    "rulebook_rulesets"
                ] = activation.rulebook.rulesets

            _update_event_streams_and_credential(self.validated_data)
        else:
            # no mappings, clear event_streams
            self.validated_data["event_streams"] = []

        if self.validated_data.get("eda_credentials"):
            _update_extra_vars_from_eda_credentials(
                validated_data=self.validated_data,
                vault_data=vault_data,
                creating=True,
            )

        if vault_data.password_used and not system_vault_credential:
            self.validated_data[
                "eda_system_vault_credential"
            ] = _create_system_eda_credential(
                vault_data.password,
                _get_vault_credential_type(),
                self.validated_data.get(
                    "organization_id", activation.organization.id
                ),
            )

    def update(
        self, instance: models.Activation, validated_data: dict
    ) -> None:
        update_fields = []
        eda_credentials = None
        event_streams = None
        for key, value in validated_data.items():
            if key == "eda_credentials":
                eda_credentials = value
                continue
            elif key == "event_streams":
                event_streams = value
                continue
            setattr(instance, key, value)
            update_fields.append(key)

        instance.save(update_fields=update_fields)
        if eda_credentials is not None:
            if eda_credentials:
                instance.eda_credentials.set(eda_credentials)
            else:
                instance.eda_credentials.clear()
        if event_streams is not None:
            if event_streams:
                instance.event_streams.set(event_streams)
            else:
                instance.event_streams.clear()

    def to_representation(self, activation):
        extra_var = (
            replace_vault_data(activation.extra_var)
            if activation.extra_var
            else None
        )
        eda_credentials = [
            credential.id for credential in activation.eda_credentials.all()
        ]

        return {
            "name": activation.name,
            "description": activation.description,
            "decision_environment_id": activation.decision_environment_id,
            "rulebook_id": activation.rulebook_id,
            "extra_var": extra_var,
            "organization_id": activation.organization_id,
            "restart_policy": activation.restart_policy,
            "awx_token_id": activation.awx_token_id,
            "log_level": activation.log_level,
            "eda_credentials": eda_credentials,
            "k8s_service_name": activation.k8s_service_name,
            "source_mappings": activation.source_mappings,
            "skip_audit_events": activation.skip_audit_events,
        }


class ActivationInstanceSerializer(serializers.ModelSerializer):
    """Serializer for the Activation Instance model."""

    queue_name = serializers.CharField(
        source="rulebookprocessqueue.queue_name",
        read_only=True,
        allow_null=True,
        default=None,
    )

    class Meta:
        model = models.RulebookProcess
        fields = [
            "id",
            "name",
            "status",
            "git_hash",
            "status_message",
            "activation_id",
            "organization_id",
            "started_at",
            "ended_at",
            "queue_name",
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
    ruleset_stats = YAMLSerializerField(
        required=True,
        sort_keys=False,
        help_text="The stat information about the activation",
    )
    restarted_at = serializers.DateTimeField(required=False, allow_null=True)
    eda_credentials = serializers.ListField(
        required=False,
        allow_null=True,
        child=EdaCredentialSerializer(),
    )
    k8s_service_name = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Service name of the activation",
    )
    event_streams = serializers.ListField(
        required=False,
        allow_null=True,
        child=EventStreamOutSerializer(),
    )
    log_tracking_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Log tracking ID of the activation",
    )
    created_by = BasicUserFieldSerializer()
    modified_by = BasicUserFieldSerializer()
    edited_by = BasicUserFieldSerializer()

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
            "ruleset_stats",
            "rules_count",
            "rules_fired_count",
            "created_at",
            "modified_at",
            "edited_at",
            "created_by",
            "modified_by",
            "edited_by",
            "restarted_at",
            "status_message",
            "awx_token_id",
            "eda_credentials",
            "log_level",
            "k8s_service_name",
            "event_streams",
            "source_mappings",
            "skip_audit_events",
            "log_tracking_id",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
            "restarted_at",
            "log_tracking_id",
        ]

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
        eda_credentials = [
            EdaCredentialSerializer(credential).data
            for credential in activation.eda_credentials.filter(managed=False)
        ]
        extra_var = (
            replace_vault_data(activation.extra_var)
            if activation.extra_var
            else None
        )
        event_streams = [
            EventStreamOutSerializer(event_stream).data
            for event_stream in activation.event_streams.all()
        ]
        ruleset_stats = (
            YAMLSerializerField(sort_keys=False).to_representation(
                activation.ruleset_stats
            )
            if activation.ruleset_stats
            else ""
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
            "ruleset_stats": ruleset_stats,
            "rules_count": rules_count,
            "rules_fired_count": rules_fired_count,
            "created_at": activation.created_at,
            "modified_at": activation.modified_at,
            "edited_at": activation.edited_at,
            "restarted_at": restarted_at,
            "status_message": activation.status_message,
            "awx_token_id": activation.awx_token_id,
            "log_level": activation.log_level,
            "eda_credentials": eda_credentials,
            "k8s_service_name": activation.k8s_service_name,
            "event_streams": event_streams,
            "source_mappings": activation.source_mappings,
            "skip_audit_events": activation.skip_audit_events,
            "log_tracking_id": activation.log_tracking_id,
            "created_by": BasicUserSerializer(activation.created_by).data,
            "modified_by": BasicUserSerializer(activation.modified_by).data,
            "edited_by": BasicUserSerializer(activation.modified_by).data,
        }


class PostActivationSerializer(serializers.ModelSerializer):
    """Serializer for validating activations before reactivate them."""

    id = serializers.IntegerField(
        required=False,
        allow_null=True,
    )
    name = serializers.CharField(required=True)
    decision_environment_id = serializers.IntegerField(
        validators=[validators.check_if_de_exists],
        error_messages={"null": "Decision Environment is needed"},
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
        allow_blank=True,
        validators=[validators.check_if_rfc_1035_compliant],
    )

    def validate(self, data):
        _validate_credentials_and_token_and_rulebook(data=data, creating=False)
        _validate_sources_with_event_streams(data=data)
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
            "edited_at",
            "awx_token_id",
            "rulebook_id",
            "eda_credentials",
            "k8s_service_name",
            "source_mappings",
            "skip_audit_events",
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
    data["event_streams"] = [obj.id for obj in activation.event_streams.all()]
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
            "The rulebook requires a RH AAP credential.",
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

    existing_extra_var_keys = []
    existing_env_var_keys = []
    existing_file_keys = []
    extra_var = data.get("extra_var")

    try:
        vault = _get_vault_credential_type()
        if extra_var:
            existing_data = yaml.safe_load(extra_var)
            existing_extra_var_keys = [*existing_data.keys()]
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

            _check_injectors(
                eda_credential, existing_extra_var_keys, "extra_vars"
            )
            _check_injectors(eda_credential, existing_file_keys, "file")
            _check_injectors(eda_credential, existing_env_var_keys, "env")
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


def _validate_sources_with_event_streams(data: dict) -> None:
    """Ensure all event streams have matching source names."""
    source_mappings = data.get("source_mappings")
    if not source_mappings:
        return

    try:
        source_mappings = yaml.safe_load(source_mappings)
    except yaml.MarkedYAMLError as ex:
        logger.error("Invalid source mappings: %s", str(ex))
        raise serializers.ValidationError(
            {
                SOURCE_MAPPING_ERROR_KEY: [
                    f"Faild to parse source mappings: '{source_mappings}'"
                ]
            }
        ) from ex

    if not isinstance(source_mappings, list):
        raise serializers.ValidationError(
            {
                SOURCE_MAPPING_ERROR_KEY: [
                    "Input source mappings should be a list of mappings"
                ]
            }
        )

    # validate each mapping has REQUIRED_KEYS
    _validate_source_mappings(source_mappings)

    rulebook_id = data.get("rulebook_id")
    if rulebook_id is None:
        return

    try:
        rulebook = models.Rulebook.objects.get(id=rulebook_id)
    except models.Rulebook.DoesNotExist as ex:
        raise serializers.ValidationError(
            {SOURCE_MAPPING_ERROR_KEY: [f"Rulebook {rulebook_id} not found."]}
        ) from ex

    try:
        sources = build_source_list(rulebook.rulesets)
    except ParseError as ex:
        raise serializers.ValidationError(
            {SOURCE_MAPPING_ERROR_KEY: [str(ex)]}
        )

    # validate no extra mappings
    if len(source_mappings) > len(sources):
        msg = (
            f"The rulebook has {len(sources)} source(s) while you have "
            f"provided {len(source_mappings)} event streams"
        )
        raise serializers.ValidationError(
            {SOURCE_MAPPING_ERROR_KEY: [str(msg)]}
        )

    # validate no duplicate sources/event_streams in provided source mappings
    for name in ["source_name", "event_stream_name"]:
        _check_duplicate_names(name, source_mappings)

    # validate rulebook is not updated during mapping
    rulebook_hash = get_rulebook_hash(rulebook.rulesets)
    for source_map in source_mappings:
        if source_map["rulebook_hash"] != rulebook_hash:
            msg = (
                "Rulebook has changed since the sources were mapped. "
                "Please reattach event streams"
            )

            raise serializers.ValidationError(
                {SOURCE_MAPPING_ERROR_KEY: [msg]}
            )

    # validate source_name provided in mapping exists in sources
    source_names = [source["name"] for source in sources]
    for source_map in source_mappings:
        if source_map["source_name"] not in source_names:
            msg = f"The source {source_map['source_name']} does not exist"
            raise serializers.ValidationError(
                {SOURCE_MAPPING_ERROR_KEY: [msg]}
            )

    # validate event_stream ids and names
    data["event_streams"] = _get_event_stream_ids(source_mappings)


def _validate_source_mappings(mappings: list[dict]) -> None:
    for mapping in mappings:
        missing_keys = [key for key in REQUIRED_KEYS if key not in mapping]

        if missing_keys:
            msg = (
                f"The source mapping {mapping} is missing the required keys: "
                f"{missing_keys}"
            )
            raise serializers.ValidationError(
                {SOURCE_MAPPING_ERROR_KEY: [msg]}
            )


def _get_event_stream_ids(source_mappings: list[dict]) -> set:
    """Get all the event stream ids from source mappings."""
    event_stream_ids = set()
    for source_map in source_mappings:
        try:
            event_stream = models.EventStream.objects.get(
                id=source_map["event_stream_id"]
            )
            if event_stream.name != source_map["event_stream_name"]:
                msg = (
                    f"Event stream {source_map['event_stream_name']} did not"
                    f" match with name {event_stream.name} in database"
                )
                raise serializers.ValidationError(
                    {SOURCE_MAPPING_ERROR_KEY: [msg]}
                )

            event_stream_ids.add(event_stream.id)
        except models.EventStream.DoesNotExist as exc:
            msg = f"Event stream id {source_map['event_stream_id']} not found"
            raise serializers.ValidationError(
                {SOURCE_MAPPING_ERROR_KEY: [msg]}
            ) from exc

    return event_stream_ids


def _check_duplicate_names(
    check_name: str, source_mappings: list[dict]
) -> None:
    msg = {"source_name": "sources", "event_stream_name": "event streams"}
    duplicate_names = set()
    names = set()

    for source_map in source_mappings:
        source_name = source_map[check_name]

        if source_name in names:
            duplicate_names.add(source_name)
        else:
            names.add(source_name)

    if len(duplicate_names) > 0:
        msg = (
            f"The following {msg.get(check_name, '')} "
            f"{', '.join(duplicate_names)} are being used multiple times"
        )
        raise serializers.ValidationError({SOURCE_MAPPING_ERROR_KEY: [msg]})


def _check_injectors(
    eda_credential: models.EdaCredential,
    existing_keys: list[str],
    injector_type: str,
) -> None:
    injectors = eda_credential.credential_type.injectors
    for key in injectors.get(injector_type, []):
        if key in existing_keys:
            message = (
                f"Key: {key} already exists in {injector_type}. "
                f"It conflicts with credential type: "
                f"{eda_credential.credential_type.name}. "
                f"Please check injectors."
            )
            raise serializers.ValidationError(message)

        existing_keys.append(key)
