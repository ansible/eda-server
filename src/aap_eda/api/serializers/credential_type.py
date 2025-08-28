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

from aap_eda.core import models, validators
from aap_eda.core.utils.credentials import validate_injectors


class CredentialTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CredentialType
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
            "managed",
        ]
        fields = [
            "name",
            "namespace",
            "kind",
            "description",
            "inputs",
            "injectors",
            *read_only_fields,
        ]


class CredentialTypeCreateSerializer(serializers.ModelSerializer):
    inputs = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Inputs of the credential type",
        validators=[validators.check_if_schema_valid],
    )
    injectors = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Injectors of the credential type",
    )

    def validate(self, data):
        injectors = data.get("injectors")
        inputs = data.get("inputs")

        if self.partial:
            inputs = inputs or self.instance.inputs

        if injectors or injectors == {}:
            errors = validate_injectors(inputs, injectors)
            if bool(errors):
                raise serializers.ValidationError(errors)

        return data

    class Meta:
        model = models.CredentialType
        fields = [
            "name",
            "description",
            "inputs",
            "injectors",
        ]


class CredentialTypeRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CredentialType
        fields = ["id", "name", "namespace", "kind"]


class CredentialTypeTestSerializer(serializers.ModelSerializer):
    inputs = serializers.JSONField(
        required=True,
        help_text="Inputs of the credential type for test",
    )
    metadata = serializers.JSONField(
        required=False,
        help_text="Metadata of the credential type for testing",
    )

    def validate(self, data):
        metadata = data.get("metadata", {})
        inputs = data.get("inputs")

        validators.check_credential_test_data(self.instance, inputs, metadata)
        return data

    class Meta:
        model = models.CredentialType
        fields = [
            "inputs",
            "metadata",
        ]
