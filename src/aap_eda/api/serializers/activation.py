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
from dataclasses import dataclass, field
from typing import Optional

import yaml
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from aap_eda.api.constants import (
    EDA_SERVER_VAULT_LABEL,
    SOURCE_MAPPING_ERROR_KEY,
)
from aap_eda.api.exceptions import ExternalSMSError, InvalidEventStreamSource
from aap_eda.api.serializers.decision_environment import (
    DecisionEnvironmentRefSerializer,
)
from aap_eda.api.serializers.eda_credential import EdaCredentialSerializer
from aap_eda.api.serializers.event_stream import EventStreamOutSerializer
from aap_eda.api.serializers.fields.basic_user import BasicUserFieldSerializer
from aap_eda.api.serializers.fields.yaml import YAMLSerializerField
from aap_eda.api.serializers.mixins import OrganizationIdFieldMixin
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
from aap_eda.core.exceptions import CredentialPluginError, ParseError
from aap_eda.core.models.utils import get_default_rule_engine_credential
from aap_eda.core.utils.credentials import (
    get_resolved_secrets,
    get_secret_fields,
)
from aap_eda.core.utils.k8s_service_name import create_k8s_service_name
from aap_eda.core.utils.rulebook import (
    build_source_list,
    get_rulebook_hash,
    swap_event_stream_sources,
    update_event_stream_sources_from_mappings,
)
from aap_eda.core.utils.strings import substitute_variables

logger = logging.getLogger(__name__)
DE_NEEDED_MSG = "Decision Environment is needed"
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
    password: str = field(default_factory=secrets.token_urlsafe)
    password_used: bool = False


def _update_event_stream_source(validated_data: dict) -> str:
    try:
        return update_event_stream_sources_from_mappings(
            validated_data["rulebook_rulesets"],
            validated_data["source_mappings"],
            PG_NOTIFY_DSN,
        )
    except Exception as e:
        logger.error("Failed to update event stream source in rulesets: %s", str(e))
        raise InvalidEventStreamSource(e) from e


def _update_k8s_service_name(validated_data: dict) -> str:
    service_name = validated_data.get("k8s_service_name")
    return service_name or create_k8s_service_name(validated_data["name"])


class _K8sPodMetadataReadFields(serializers.Serializer):
    """Read-only k8s pod-metadata field declarations (no validators)."""

    k8s_pod_service_account_name = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text=("Kubernetes ServiceAccount for activation job pods"),
    )
    k8s_pod_labels = serializers.JSONField(
        required=False,
        default=dict,
    )
    k8s_pod_annotations = serializers.JSONField(
        required=False,
        default=dict,
    )
    k8s_pod_node_selector = serializers.JSONField(
        required=False,
        default=dict,
    )

# rest of file unchanged
