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

from aap_eda.api.serializers.eda_credential import EdaCredentialRefSerializer
from aap_eda.api.serializers.organization import OrganizationRefSerializer
from aap_eda.core import models, validators


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
            "organization_id",
            "eda_credential_id",
            *read_only_fields,
        ]


class DecisionEnvironmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating the DecisionEnvironment."""

    organization_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        validators=[validators.check_if_organization_exists],
    )
    eda_credential_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        validators=[
            validators.check_credential_types_for_registry,
        ],
    )

    class Meta:
        model = models.DecisionEnvironment
        fields = [
            "name",
            "description",
            "image_url",
            "organization_id",
            "eda_credential_id",
        ]


class DecisionEnvironmentReadSerializer(serializers.ModelSerializer):
    """Serializer for reading the DecisionEnvironment with embedded objects."""

    eda_credential = EdaCredentialRefSerializer(
        required=False, allow_null=True
    )
    organization = OrganizationRefSerializer()

    class Meta:
        model = models.DecisionEnvironment
        fields = [
            "id",
            "name",
            "description",
            "image_url",
            "organization",
            "eda_credential",
            "created_at",
            "modified_at",
        ]
        read_only_fields = ["id", "created_at", "modified_at"]

    def to_representation(self, decision_environment):
        eda_credential = (
            EdaCredentialRefSerializer(
                decision_environment["eda_credential"]
            ).data
            if decision_environment["eda_credential"]
            else None
        )
        organization = (
            OrganizationRefSerializer(
                decision_environment["organization"]
            ).data
            if decision_environment["organization"]
            else None
        )
        return {
            "id": decision_environment["id"],
            "name": decision_environment["name"],
            "description": decision_environment["description"],
            "image_url": decision_environment["image_url"],
            "organization": organization,
            "eda_credential": eda_credential,
            "created_at": decision_environment["created_at"],
            "modified_at": decision_environment["modified_at"],
        }


class DecisionEnvironmentRefSerializer(serializers.ModelSerializer):
    """Serializer for DecisionEnvironment reference."""

    class Meta:
        model = models.DecisionEnvironment
        fields = ["id", "name", "description", "image_url", "organization_id"]
        read_only_fields = ["id"]
