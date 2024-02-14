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

from aap_eda.api.serializers.credential import CredentialRefSerializer
from aap_eda.core import models


class DecisionEnvironmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DecisionEnvironment
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
        ]
        fields = [
            "name",
            "description",
            "image_url",
            "credential_id",
            "organization_id",
            *read_only_fields,
        ]


class DecisionEnvironmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating the DecisionEnvironment."""

    credential_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = models.DecisionEnvironment
        fields = [
            "name",
            "description",
            "image_url",
            "credential_id",
            "organization_id",
        ]


class DecisionEnvironmentReadSerializer(serializers.ModelSerializer):
    """Serializer for reading the DecisionEnvironment with embedded objects."""

    credential = CredentialRefSerializer(required=False, allow_null=True)

    class Meta:
        model = models.DecisionEnvironment()
        fields = [
            "id",
            "name",
            "description",
            "image_url",
            "credential",
            "organization_id",
            "created_at",
            "modified_at",
        ]
        read_only_fields = ["id", "created_at", "modified_at"]

    def to_representation(self, decision_environment):
        credential = (
            CredentialRefSerializer(decision_environment["credential"]).data
            if decision_environment["credential"]
            else None
        )
        return {
            "id": decision_environment["id"],
            "name": decision_environment["name"],
            "description": decision_environment["description"],
            "image_url": decision_environment["image_url"],
            "credential": credential,
            "organization_id": decision_environment["organization_id"],
            "created_at": decision_environment["created_at"],
            "modified_at": decision_environment["modified_at"],
        }


class DecisionEnvironmentRefSerializer(serializers.ModelSerializer):
    """Serializer for DecisionEnvironment reference."""

    class Meta:
        model = models.DecisionEnvironment
        fields = ["id", "name", "description", "image_url", "organization_id"]
        read_only_fields = ["id"]
