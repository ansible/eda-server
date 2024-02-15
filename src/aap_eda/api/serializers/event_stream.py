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

import logging
import uuid

import yaml
from django.conf import settings
from django.core.validators import RegexValidator
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from aap_eda.api.constants import (
    PG_NOTIFY_TEMPLATE_RULEBOOK_DATA,
    PG_NOTIFY_TEMPLATE_RULEBOOK_NAME,
)
from aap_eda.api.exceptions import (
    MissingEventStreamRulebook,
    MissingEventStreamRulebookKeys,
    MissingEventStreamRulebookSource,
)
from aap_eda.api.serializers.credential import CredentialSerializer
from aap_eda.api.serializers.utils import substitute_extra_vars, swap_sources
from aap_eda.core import models, validators

logger = logging.getLogger(__name__)

EDA_CHANNEL_PREFIX = "eda_"


def _get_rulebook():
    rulebook = None
    name = settings.PG_NOTIFY_TEMPLATE_RULEBOOK
    if name:
        rulebook = models.Rulebook.objects.filter(name=name).first()

        if not rulebook:
            logger.error(
                "Missing Listener rulebook %s",
                settings.PG_NOTIFY_TEMPLATE_RULEBOOK,
            )
            raise MissingEventStreamRulebook

        required_keys = ["type", "name", "args"]
        rulesets = yaml.safe_load(rulebook.rulesets)
        for ruleset in rulesets:
            sources = ruleset.get("sources", [])
            for source in sources:
                complementary_source = source.get("complementary_source")

                if not complementary_source:
                    raise MissingEventStreamRulebookSource

                for key in required_keys:
                    if key not in complementary_source.keys():
                        raise MissingEventStreamRulebookKeys

    return rulebook


def _get_default_channel_name():
    stream_uuid = str(uuid.uuid4())
    return f"{EDA_CHANNEL_PREFIX}{stream_uuid.replace('-','_')}"


def _get_extra_var_id(validated_data: dict) -> dict:
    rulesets = yaml.safe_load(validated_data["rulebook_rulesets"])
    extra_vars = rulesets[0]["sources"][0]["extra_vars"]
    extra_vars = substitute_extra_vars(
        validated_data, extra_vars, [], "password"
    )

    extra_var = models.ExtraVar.objects.create(extra_var=yaml.dump(extra_vars))
    return extra_var.id


def _updated_listener_ruleset(validated_data):
    sources_info = [
        {
            "name": validated_data["name"],
            "type": validated_data["source_type"],
            "args": validated_data["source_args"],
        }
    ]
    return swap_sources(validated_data["rulebook_rulesets"], sources_info)


class YAMLSerializerField(serializers.Field):
    """Serializer for YAML a superset of JSON."""

    def to_internal_value(self, data) -> dict:
        if data:
            try:
                parsed_args = yaml.safe_load(data)
            except yaml.YAMLError:
                raise ValidationError("Invalid YAML format for 'source_args'")

            if not isinstance(parsed_args, dict):
                raise ValidationError(
                    "The 'source_args' field must be a YAML "
                    "object (dictionary)"
                )

            return parsed_args
        return data

    def to_representation(self, value) -> str:
        return yaml.dump(value)


class EventStreamSerializer(serializers.ModelSerializer):
    decision_environment_id = serializers.IntegerField(
        validators=[validators.check_if_de_exists]
    )
    user = serializers.SerializerMethodField()
    source_args = YAMLSerializerField(required=False, allow_null=True)
    credentials = serializers.SerializerMethodField()

    class Meta:
        model = models.EventStream
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
        ]
        fields = [
            "name",
            "source_args",
            "source_type",
            "channel_name",
            "is_enabled",
            "status",
            "status_message",
            "decision_environment_id",
            "user",
            "credentials",
            *read_only_fields,
        ]

    def get_user(self, obj) -> str:
        return f"{obj.user.username}"

    def get_credentials(self, obj) -> str:
        return [
            CredentialSerializer(credential).data
            for credential in obj.credentials.all()
        ]


class EventStreamCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating the EventStream."""

    decision_environment_id = serializers.IntegerField(
        validators=[validators.check_if_de_exists]
    )
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    source_args = YAMLSerializerField()
    channel_name = serializers.CharField(
        default=_get_default_channel_name,
        validators=[
            RegexValidator(
                regex=r"^\w+$",
                message="Channel name can only contain alphanumeric and "
                "underscore characters",
            ),
        ],
    )
    credentials = serializers.ListField(
        required=False,
        allow_null=True,
        child=serializers.IntegerField(),
    )

    class Meta:
        model = models.EventStream
        fields = [
            "name",
            "description",
            "is_enabled",
            "source_type",
            "source_args",
            "channel_name",
            "decision_environment_id",
            "rulebook_id",
            "extra_var_id",
            "user",
            "restart_policy",
            "credentials",
        ]

    def create(self, validated_data):
        rulebook = _get_rulebook()
        validated_data["user_id"] = validated_data["user"].id
        if rulebook:
            validated_data["rulebook_name"] = rulebook.name
            validated_data["rulebook_id"] = rulebook.id
            validated_data["rulebook_rulesets"] = rulebook.rulesets
        else:
            validated_data["rulebook_name"] = PG_NOTIFY_TEMPLATE_RULEBOOK_NAME
            validated_data["rulebook_id"] = None
            validated_data[
                "rulebook_rulesets"
            ] = PG_NOTIFY_TEMPLATE_RULEBOOK_DATA

        validated_data["channel_name"] = validated_data.get(
            "channel_name", _get_default_channel_name()
        )
        validated_data["extra_var_id"] = _get_extra_var_id(validated_data)
        validated_data["rulebook_rulesets"] = _updated_listener_ruleset(
            validated_data
        )
        return super().create(validated_data)


class EventStreamOutSerializer(serializers.ModelSerializer):
    """Serializer for UI to show EventStream."""

    class Meta:
        model = models.EventStream
        fields = ["id", "name"]
