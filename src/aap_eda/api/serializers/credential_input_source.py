"""Serializer for CredentialInputSource."""
#  Copyright 2025 Red Hat, Inc.
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
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from aap_eda.api.serializers.eda_credential import EdaCredentialReferenceField
from aap_eda.api.serializers.fields.basic_user import BasicUserFieldSerializer
from aap_eda.api.serializers.organization import OrganizationRefSerializer
from aap_eda.api.serializers.user import BasicUserSerializer
from aap_eda.core import models, validators
from aap_eda.core.utils.credentials import inputs_to_display, validate_inputs
from aap_eda.core.utils.crypto.base import SecretValue


class CredentialInputSourceReferenceSerializer(serializers.Serializer):
    """CredentialInpuSource Reference Serializer."""

    type = serializers.CharField(
        required=True, help_text="Type of the related resource"
    )
    id = serializers.IntegerField(
        required=True, help_text="ID of the related resource"
    )
    name = serializers.CharField(
        required=True, help_text="Name of the related resource"
    )
    uri = serializers.URLField(
        required=True, help_text="URI of the related resource"
    )


@extend_schema_field(CredentialInputSourceReferenceSerializer(many=True))
class CredentialInputSourceReferenceField(serializers.JSONField):
    pass


class CredentialInputSourceSerializer(serializers.ModelSerializer):
    """Serializer used during a GET."""

    organization = OrganizationRefSerializer()
    references = EdaCredentialReferenceField(required=False, allow_null=True)
    created_by = BasicUserFieldSerializer()
    modified_by = BasicUserFieldSerializer()

    class Meta:
        model = models.CredentialInputSource
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
            "organization",
        ]
        fields = [
            "description",
            "metadata",
            "references",
            "created_by",
            "modified_by",
            "input_field_name",
            "source_credential",
            "target_credential",
            *read_only_fields,
        ]

    def to_representation(self, instance):
        organization = (
            OrganizationRefSerializer(instance.organization).data
            if instance.organization
            else None
        )

        if not hasattr(self, "references"):
            self.references = None

        return {
            "id": instance.id,
            "source_credential": instance.source_credential.id,
            "target_credential": instance.target_credential.id,
            "input_field_name": instance.input_field_name,
            "metadata": _get_metadata(instance),
            "organization": organization,
            "references": self.references,
            "created_at": instance.created_at,
            "modified_at": instance.modified_at,
            "created_by": BasicUserSerializer(instance.created_by).data,
            "modified_by": BasicUserSerializer(instance.modified_by).data,
        }


class CredentialInputSourceCreateSerializer(serializers.ModelSerializer):
    """Serializer used during the Create process of the instance."""

    target_credential = serializers.PrimaryKeyRelatedField(
        queryset=models.EdaCredential.objects.all(),
        required=True,
        allow_null=False,
        error_messages={
            "required": "Target Credential is required",
            "does_not_exist": "Target Credential does not exist",
            "incorrect_type": "Expected an integer value.",
        },
    )
    source_credential = serializers.PrimaryKeyRelatedField(
        queryset=models.EdaCredential.objects.all(),
        required=True,
        allow_null=False,
        error_messages={
            "required": "Source Credential is required",
            "does_not_exist": "Source Credential does not exist",
            "incorrect_type": "Expected an integer value.",
        },
    )
    organization_id = serializers.IntegerField(
        required=True,
        allow_null=False,
        validators=[validators.check_if_organization_exists],
        error_messages={
            "null": "Organization is needed",
            "required": "Organization is required",
        },
    )
    metadata = serializers.JSONField()

    def validate(self, attrs):
        metadata = attrs.get("metadata", {})
        errors = validate_inputs(
            attrs["source_credential"].credential_type,
            attrs["source_credential"].credential_type.inputs,
            metadata,
            "metadata",
        )
        if bool(errors):
            raise serializers.ValidationError(errors)

        validators.check_if_field_exists(
            attrs["target_credential"].credential_type.inputs,
            attrs.get("input_field_name"),
        )

        return attrs

    class Meta:
        model = models.CredentialInputSource
        fields = [
            "description",
            "metadata",
            "target_credential",
            "source_credential",
            "input_field_name",
            "organization_id",
        ]


class CredentialInputSourceUpdateSerializer(serializers.ModelSerializer):
    """Serializer used during update of the instance."""

    organization_id = serializers.IntegerField(
        required=True,
        allow_null=False,
        validators=[validators.check_if_organization_exists],
        error_messages={"null": "Organization is needed"},
    )
    metadata = serializers.JSONField()

    def validate(self, attrs):
        credential_type = self.instance.source_credential.credential_type

        metadata = attrs.get("metadata", {})
        if bool(metadata):
            errors = validate_inputs(
                credential_type, credential_type.inputs, metadata, "metadata"
            )
            if bool(errors):
                raise serializers.ValidationError(errors)

        return attrs

    class Meta:
        model = models.CredentialInputSource
        fields = [
            "description",
            "metadata",
            "organization_id",
            "source_credential",
            "target_credential",
            "input_field_name",
        ]


class CredentialInputSourceRefSerializer(serializers.ModelSerializer):
    """Serializer for CredentialInputSource reference."""

    class Meta:
        model = models.CredentialInputSource
        fields = [
            "id",
            "description",
            "organization_id",
            "source_credential",
            "target_credential",
        ]
        read_only_fields = ["id"]


def _get_metadata(instance) -> dict:
    metadata = (
        instance.metadata.get_secret_value()
        if isinstance(instance.metadata, SecretValue)
        else instance.metadata
    )
    return inputs_to_display(
        instance.source_credential.credential_type.inputs, metadata, "metadata"
    )
