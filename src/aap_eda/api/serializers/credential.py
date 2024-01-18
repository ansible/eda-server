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

from rest_framework import serializers

from aap_eda.api.constants import EDA_SERVER_VAULT_LABEL
from aap_eda.core import models
from aap_eda.core.enums import CredentialType


class CredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Credential
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
        ]
        fields = [
            "name",
            "description",
            "username",
            "credential_type",
            "key",
            *read_only_fields,
        ]


class CredentialCreateSerializer(serializers.ModelSerializer):
    secret = serializers.CharField(required=True, allow_null=False)

    def validate(self, data):
        key_required_types = [
            CredentialType.EXTRA_VAR,
            CredentialType.VAULT_PASSWORD,
        ]
        credential_type = data.get("credential_type", CredentialType.REGISTRY)
        # TODO: may need to change `key` to `variable_name` later
        key = data.get("key")

        if credential_type in key_required_types and key is None:
            raise serializers.ValidationError(
                f"Key field is required when type is {credential_type}"
            )

        if (
            credential_type == CredentialType.VAULT_PASSWORD
            and key == EDA_SERVER_VAULT_LABEL
        ):
            raise serializers.ValidationError(
                f"{key} is reserved by EDA for vault labels"
            )

        if credential_type == CredentialType.EXTRA_VAR:
            credentials = models.Credential.objects.filter(
                credential_type=credential_type
            )
            if key in [credential.key for credential in credentials]:
                raise serializers.ValidationError(
                    f"Duplicate {key} found in credentials"
                )

        return data

    class Meta:
        model = models.Credential
        fields = [
            "name",
            "description",
            "credential_type",
            "username",
            "key",
            "secret",
        ]


class CredentialRefSerializer(serializers.ModelSerializer):
    """Serializer for Credential reference."""

    class Meta:
        model = models.Credential
        fields = [
            "id",
            "name",
            "description",
            "credential_type",
            "username",
            "key",
        ]
        read_only_fields = ["id"]
