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

import yaml
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from aap_eda.core import models


class SourceSerializer(serializers.ModelSerializer):
    decision_environment_id = serializers.IntegerField(
        required=False,
        allow_null=True,
    )

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = models.Source
        read_only_fields = [
            "id",
            "uuid",
            "created_at",
            "modified_at",
        ]
        fields = [
            "name",
            "args",
            "type",
            "decision_environment_id",
            "user",
            *read_only_fields,
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def validate_args(self, value):
        if value:
            try:
                parsed_args = yaml.safe_load(value)
            except yaml.YAMLError:
                raise ValidationError("Invalid YAML format for 'args'")

            if not isinstance(parsed_args, dict):
                raise ValidationError(
                    "The 'args' field must be a YAML object (dictionary)"
                )

            return parsed_args
        return value


class SourceOutSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    args = serializers.SerializerMethodField()

    class Meta:
        model = models.Source
        read_only_fields = [
            "id",
            "uuid",
            "created_at",
            "modified_at",
        ]
        fields = [
            "name",
            "args",
            "type",
            "is_enabled",
            "restart_policy",
            "activation_id",
            "decision_environment_id",
            "user",
            *read_only_fields,
        ]

    def get_user(self, obj) -> str:
        return f"{obj.user.username}"

    def get_args(self, obj) -> str:
        return f"{yaml.dump(obj.args)}"
