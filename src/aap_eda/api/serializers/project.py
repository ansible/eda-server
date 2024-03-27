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
from rest_framework.validators import UniqueValidator

from aap_eda.api.serializers.eda_credential import EdaCredentialRefSerializer
from aap_eda.api.serializers.organization import OrganizationRefSerializer
from aap_eda.core import models, validators


class ProjectSerializer(serializers.ModelSerializer):
    eda_credential_id = serializers.IntegerField(
        required=False, allow_null=True
    )

    class Meta:
        model = models.Project
        read_only_fields = [
            "id",
            "url",
            "scm_type",
            "git_hash",
            "import_state",
            "import_error",
            "created_at",
            "modified_at",
        ]
        fields = [
            "name",
            "description",
            "organization_id",
            "eda_credential_id",
            "signature_validation_credential_id",
            "scm_branch",
            "scm_refspec",
            "verify_ssl",
            *read_only_fields,
        ]


class ProjectCreateRequestSerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(required=False, allow_null=True)
    eda_credential_id = serializers.IntegerField(
        required=False, allow_null=True
    )
    signature_validation_credential_id = serializers.IntegerField(
        required=False, allow_null=True
    )

    class Meta:
        model = models.Project
        fields = [
            "url",
            "name",
            "description",
            "organization_id",
            "eda_credential_id",
            "signature_validation_credential_id",
            "verify_ssl",
            "scm_type",
            "scm_branch",
            "scm_refspec",
        ]


class ProjectUpdateRequestSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=False,
        allow_blank=False,
        allow_null=False,
        help_text="Name of the project",
        validators=[
            UniqueValidator(
                queryset=models.Project.objects.all(),
                message="Project with this name already exists.",
            )
        ],
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Description of the project",
    )
    eda_credential_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="EdaCredential id of the project",
    )
    signature_validation_credential_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text=(
            "ID of an optional credential used for validating files in the "
            "project against unexpected changes"
        ),
    )
    verify_ssl = serializers.BooleanField(
        required=False,
        help_text="Indicates if SSL verification is enabled",
    )
    scm_branch = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Specific branch, tag or commit to checkout.",
    )
    scm_refspec = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="For git projects, an additional refspec to fetch.",
    )

    class Meta:
        model = models.Project
        fields = [
            "name",
            "description",
            "eda_credential_id",
            "signature_validation_credential_id",
            "scm_branch",
            "scm_refspec",
            "verify_ssl",
        ]


class ProjectReadSerializer(serializers.ModelSerializer):
    """Serializer for reading the Project with embedded objects."""

    organization = OrganizationRefSerializer()
    eda_credential = EdaCredentialRefSerializer(
        required=False, allow_null=True
    )
    signature_validation_credential = EdaCredentialRefSerializer(
        required=False, allow_null=True
    )

    class Meta:
        model = models.Project
        read_only_fields = [
            "id",
            "url",
            "scm_type",
            "git_hash",
            "import_state",
            "import_error",
            "created_at",
            "modified_at",
        ]
        fields = [
            "name",
            "description",
            "organization",
            "eda_credential",
            "signature_validation_credential",
            "verify_ssl",
            "scm_branch",
            "scm_refspec",
            *read_only_fields,
        ]

    def to_representation(self, project):
        eda_credential = (
            EdaCredentialRefSerializer(project["eda_credential"]).data
            if project["eda_credential"]
            else None
        )
        signature_validation_credential = (
            EdaCredentialRefSerializer(
                project["signature_validation_credential"]
            ).data
            if project["signature_validation_credential"]
            else None
        )
        organization = (
            OrganizationRefSerializer(project["organization"]).data
            if project["organization"]
            else None
        )
        return {
            "id": project["id"],
            "name": project["name"],
            "description": project["description"],
            "url": project["url"],
            "scm_type": project["scm_type"],
            "scm_branch": project["scm_branch"],
            "scm_refspec": project["scm_refspec"],
            "git_hash": project["git_hash"],
            "verify_ssl": project["verify_ssl"],
            "organization": organization,
            "eda_credential": eda_credential,
            "signature_validation_credential": signature_validation_credential,
            "import_state": project["import_state"],
            "import_error": project["import_error"],
            "created_at": project["created_at"],
            "modified_at": project["modified_at"],
        }


class ProjectRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Project
        fields = [
            "id",
            "git_hash",
            "url",
            "scm_type",
            "name",
            "description",
            "organization_id",
        ]
        read_only_fields = ["id"]


class ExtraVarSerializer(serializers.ModelSerializer):
    extra_var = serializers.CharField(
        required=True,
        help_text="Content of the extra_var",
        validators=[validators.is_extra_var_dict],
    )

    class Meta:
        model = models.ExtraVar
        fields = ["id", "extra_var", "organization_id"]
        read_only_fields = ["id"]


class ExtraVarCreateSerializer(serializers.ModelSerializer):
    extra_var = serializers.CharField(
        required=True,
        help_text="Content of the extra_var",
    )
    organization_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = models.ExtraVar
        fields = ["extra_var", "organization_id"]


class ExtraVarRefSerializer(serializers.ModelSerializer):
    """Serializer for Extra Var reference."""

    class Meta:
        model = models.ExtraVar
        fields = ["id"]
        read_only_fields = ["id"]
