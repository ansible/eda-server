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

from aap_eda.api.serializers.credential_type import CredentialTypeRefSerializer
from aap_eda.core import models
from aap_eda.core.utils.credentials import inputs_to_display, validate_inputs
from aap_eda.core.utils.crypto.base import SecretValue


class EdaCredentialSerializer(serializers.ModelSerializer):
    inputs = serializers.SerializerMethodField()
    credential_type = CredentialTypeRefSerializer(
        required=False, allow_null=True
    )

    class Meta:
        model = models.EdaCredential
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
            "managed",
        ]
        fields = [
            "name",
            "description",
            "inputs",
            "credential_type",
            *read_only_fields,
        ]

    def get_inputs(self, obj) -> str:
        return _get_inputs(obj)

    def to_representation(self, eda_credential):
        credential_type = (
            CredentialTypeRefSerializer(eda_credential.credential_type).data
            if eda_credential.credential_type
            else None
        )
        return {
            "id": eda_credential.id,
            "name": eda_credential.name,
            "description": eda_credential.description,
            "managed": eda_credential.managed,
            "inputs": self.get_inputs(eda_credential),
            "credential_type": credential_type,
            "created_at": eda_credential.created_at,
            "modified_at": eda_credential.modified_at,
        }


class EdaCredentialCreateSerializer(serializers.ModelSerializer):
    credential_type_id = serializers.IntegerField(
        required=True, allow_null=True
    )
    inputs = serializers.JSONField()

    def validate(self, data):
        credential_type_id = data.get("credential_type_id")
        if credential_type_id:
            credential_type = models.CredentialType.objects.get(
                id=credential_type_id
            )
        else:
            # for update
            credential_type = self.instance.credential_type

        errors = validate_inputs(credential_type.inputs, data["inputs"])
        if bool(errors):
            raise serializers.ValidationError(errors)

        return data

    class Meta:
        model = models.EdaCredential
        read_only_fields = [
            "id",
            "managed",
            "created_at",
            "modified_at",
        ]
        fields = [
            "id",
            "name",
            "description",
            "inputs",
            "credential_type_id",
            "created_at",
            "modified_at",
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
