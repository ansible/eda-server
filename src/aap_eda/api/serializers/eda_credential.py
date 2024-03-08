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

from rest_framework import serializers

from aap_eda.core import models
from aap_eda.core.utils.credentials import inputs_to_display
from aap_eda.core.utils.crypto.base import SecretValue


class EdaCredentialSerializer(serializers.ModelSerializer):
    inputs = serializers.SerializerMethodField()

    class Meta:
        model = models.EdaCredential
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
        ]
        fields = [
            "name",
            "description",
            "inputs",
            "managed",
            "credential_type_id",
            *read_only_fields,
        ]

    def get_inputs(self, obj) -> str:
        return _get_inputs(obj)


class EdaCredentialUpdateSerializer(serializers.ModelSerializer):
    inputs = serializers.JSONField()

    class Meta:
        model = models.EdaCredential
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
        ]
        fields = [
            "name",
            "description",
            "inputs",
            "managed",
            "credential_type_id",
            *read_only_fields,
        ]


class EdaCredentialCreateSerializer(serializers.ModelSerializer):
    credential_type_id = serializers.IntegerField(
        required=True, allow_null=True
    )
    inputs = serializers.JSONField()

    def validate(self, data):
        # TODO: add validation later
        return data

    class Meta:
        model = models.EdaCredential
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
        ]
        fields = [
            "name",
            "description",
            "inputs",
            "managed",
            "credential_type_id",
            *read_only_fields,
        ]


class EdaCredentialRefSerializer(serializers.ModelSerializer):
    """Serializer for EdaCredential reference."""

    inputs = serializers.SerializerMethodField()

    class Meta:
        model = models.EdaCredential
        fields = [
            "id",
            "name",
            "description",
            "inputs",
            "managed",
            "credential_type_id",
        ]
        read_only_fields = ["id"]

    def get_inputs(self, obj) -> str:
        return _get_inputs(obj)


def _get_inputs(obj) -> str:
    inputs = (
        obj.inputs.get_secret_value()
        if isinstance(obj.inputs, SecretValue)
        else obj.inputs
    )
    return inputs_to_display(
        obj.credential_type.inputs,
        inputs,
    )
