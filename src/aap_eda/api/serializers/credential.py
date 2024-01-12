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

from aap_eda.core import models


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
            *read_only_fields,
        ]


class CredentialCreateSerializer(serializers.ModelSerializer):
    secret = serializers.CharField(required=True, allow_null=False)

    class Meta:
        model = models.Credential
        fields = [
            "name",
            "description",
            "credential_type",
            "username",
            "secret",
        ]


class CredentialRefSerializer(serializers.ModelSerializer):
    """Serializer for Credential reference."""

    class Meta:
        model = models.Credential
        fields = ["id", "name", "description", "credential_type", "username"]
        read_only_fields = ["id"]
