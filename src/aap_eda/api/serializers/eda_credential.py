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

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from aap_eda.api.serializers.credential_type import CredentialTypeRefSerializer
from aap_eda.api.serializers.organization import OrganizationRefSerializer
from aap_eda.core import models, validators
from aap_eda.core.utils.credentials import inputs_to_display, validate_inputs
from aap_eda.core.utils.crypto.base import SecretValue


class EdaCredentialReferenceSerializer(serializers.Serializer):
    type = serializers.CharField(
        required=True, help_text="Type of the related resource"
    )
    id = serializers.IntegerField(
        required=True, help_text="ID of the related resource"
    )
    name = serializers.CharField(
        required=True, help_text="Name of the related resource"
    )
    url = serializers.URLField(
        required=True, help_text="URL of the related resource"
    )


@extend_schema_field(EdaCredentialReferenceSerializer(many=True))
class EdaCredentialReferenceField(serializers.JSONField):
    pass


class EdaCredentialSerializer(serializers.ModelSerializer):
    inputs = serializers.SerializerMethodField()
    credential_type = CredentialTypeRefSerializer(
        required=False, allow_null=True
    )
    organization = OrganizationRefSerializer()
    references = EdaCredentialReferenceField(required=False, allow_null=True)

    class Meta:
        model = models.EdaCredential
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
            "managed",
            "organization",
        ]
        fields = [
            "name",
            "description",
            "inputs",
            "credential_type",
            "references",
            *read_only_fields,
        ]

    def get_inputs(self, obj) -> dict:
        return _get_inputs(obj)

    def to_representation(self, eda_credential):
        credential_type = (
            CredentialTypeRefSerializer(eda_credential.credential_type).data
            if eda_credential.credential_type
            else None
        )
        organization = (
            OrganizationRefSerializer(eda_credential.organization).data
            if eda_credential.organization
            else None
        )

        if not hasattr(self, "references"):
            self.references = None

        return {
            "id": eda_credential.id,
            "name": eda_credential.name,
            "description": eda_credential.description,
            "managed": eda_credential.managed,
            "inputs": self.get_inputs(eda_credential),
            "credential_type": credential_type,
            "organization": organization,
            "references": self.references,
            "created_at": eda_credential.created_at,
            "modified_at": eda_credential.modified_at,
        }


class EdaCredentialCreateSerializer(serializers.ModelSerializer):
    credential_type_id = serializers.IntegerField(
        required=True,
        allow_null=True,
        validators=[validators.check_if_credential_type_exists],
    )
    organization_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        validators=[validators.check_if_organization_exists],
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

        inputs = data.get("inputs")
        if inputs:
            errors = validate_inputs(credential_type.inputs, inputs)
            if bool(errors):
                raise serializers.ValidationError(errors)

        return data

    class Meta:
        model = models.EdaCredential
        fields = [
            "name",
            "description",
            "inputs",
            "credential_type_id",
            "organization_id",
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
            "organization_id",
        ]
        read_only_fields = ["id"]

    def get_inputs(self, obj) -> dict:
        return _get_inputs(obj)


def _get_inputs(obj) -> dict:
    inputs = (
        obj.inputs.get_secret_value()
        if isinstance(obj.inputs, SecretValue)
        else obj.inputs
    )
    return inputs_to_display(
        obj.credential_type.inputs,
        inputs,
    )


def get_references(eda_credential: models.EdaCredential) -> list[dict]:
    resources = []

    used_activations = eda_credential.activations.all()
    used_decision_environments = models.DecisionEnvironment.objects.filter(
        eda_credential=eda_credential
    )
    used_projects = models.Project.objects.filter(
        eda_credential=eda_credential
    )

    for activation in used_activations:
        resource = {
            "type": "Activation",
            "id": activation.id,
            "name": activation.name,
            "url": f"api/eda/v1/activations/{activation.id}/",
        }
        resources.append(resource)

    for decision_environment in used_decision_environments:
        resource = {
            "type": "DecisionEnvironment",
            "id": decision_environment.id,
            "name": decision_environment.name,
            "url": (
                f"api/eda/v1/decision-environments/{decision_environment.id}/"
            ),
        }
        resources.append(resource)

    for project in used_projects:
        resource = {
            "type": "Project",
            "id": project.id,
            "name": project.name,
            "url": f"api/eda/v1/projects/{project.id}/",
        }
        resources.append(resource)

    return resources
