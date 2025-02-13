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

from urllib.parse import urlparse, urlunparse

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from aap_eda.api.serializers.eda_credential import EdaCredentialRefSerializer
from aap_eda.api.serializers.fields.basic_user import BasicUserFieldSerializer
from aap_eda.api.serializers.organization import OrganizationRefSerializer
from aap_eda.api.serializers.user import BasicUserSerializer
from aap_eda.core import models, validators
from aap_eda.core.utils.crypto.base import SecretValue

ENCRYPTED_STRING = "$encrypted$"
ANSIBLE_VAULT_STRING = "$ANSIBLE_VAULT;"


class ProxyFieldMixin:
    def get_proxy(self, obj: models.Project) -> str:
        if not obj.proxy:
            return ""
        url = obj.proxy
        if isinstance(url, SecretValue):
            url = obj.proxy.get_secret_value()
        return get_proxy_for_display(url)


class ProjectSerializer(serializers.ModelSerializer, ProxyFieldMixin):
    eda_credential_id = serializers.IntegerField(
        required=False, allow_null=True
    )

    proxy = serializers.SerializerMethodField()
    created_by = BasicUserFieldSerializer()
    modified_by = BasicUserFieldSerializer()

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
            "proxy",
            "created_by",
            "modified_by",
            *read_only_fields,
        ]

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result["created_by"] = BasicUserSerializer(instance.created_by).data
        result["modified_by"] = BasicUserSerializer(instance.modified_by).data
        return result


class ProjectCreateRequestSerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(
        required=True,
        allow_null=False,
        validators=[validators.check_if_organization_exists],
        error_messages={
            "null": "Organization is needed",
            "required": "Organization is required",
        },
    )
    eda_credential_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        validators=[
            validators.check_credential_types_for_scm,
        ],
    )
    signature_validation_credential_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        validators=[validators.check_credential_types_for_gpg],
    )

    class Meta:
        model = models.Project
        fields = [
            "url",
            "proxy",
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
    organization_id = serializers.IntegerField(
        required=True,
        allow_null=False,
        validators=[validators.check_if_organization_exists],
        error_messages={
            "null": "Organization is needed",
            "required": "Organization is required",
        },
    )
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
        validators=[
            validators.check_credential_types_for_scm,
        ],
    )
    signature_validation_credential_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text=(
            "ID of an optional credential used for validating files in the "
            "project against unexpected changes"
        ),
        validators=[
            validators.check_credential_types_for_gpg,
        ],
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
    proxy = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Proxy server for http or https connection",
    )

    class Meta:
        model = models.Project
        fields = [
            "name",
            "description",
            "organization_id",
            "eda_credential_id",
            "signature_validation_credential_id",
            "scm_branch",
            "scm_refspec",
            "verify_ssl",
            "proxy",
        ]

    def validate(self, data):
        if "proxy" in data and ENCRYPTED_STRING in data["proxy"]:
            project = self.instance
            unchanged = (
                project.proxy
                and get_proxy_for_display(project.proxy.get_secret_value())
                == data["proxy"]
            )
            if unchanged:
                data.pop("proxy")
            else:
                raise serializers.ValidationError(
                    "The password in the proxy field should be unencrypted"
                )
        return data

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result["created_by"] = BasicUserSerializer(instance.created_by).data
        result["modified_by"] = BasicUserSerializer(instance.modified_by).data
        return result


class ProjectReadSerializer(serializers.ModelSerializer, ProxyFieldMixin):
    """Serializer for reading the Project with embedded objects."""

    organization = OrganizationRefSerializer()
    eda_credential = EdaCredentialRefSerializer(
        required=False, allow_null=True
    )
    signature_validation_credential = EdaCredentialRefSerializer(
        required=False, allow_null=True
    )
    proxy = serializers.SerializerMethodField()
    created_by = BasicUserFieldSerializer()
    modified_by = BasicUserFieldSerializer()

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
            "proxy",
            "created_by",
            "modified_by",
            *read_only_fields,
        ]

    def to_representation(self, project):
        eda_credential = (
            EdaCredentialRefSerializer(project.eda_credential).data
            if project.eda_credential
            else None
        )
        signature_validation_credential = (
            EdaCredentialRefSerializer(
                project.signature_validation_credential
            ).data
            if project.signature_validation_credential
            else None
        )
        organization = (
            OrganizationRefSerializer(project.organization).data
            if project.organization
            else None
        )

        return {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "url": project.url,
            "proxy": self.get_proxy(project),
            "scm_type": project.scm_type,
            "scm_branch": project.scm_branch,
            "scm_refspec": project.scm_refspec,
            "git_hash": project.git_hash,
            "verify_ssl": project.verify_ssl,
            "organization": organization,
            "eda_credential": eda_credential,
            "signature_validation_credential": signature_validation_credential,
            "import_state": project.import_state,
            "import_error": project.import_error,
            "created_at": project.created_at,
            "modified_at": project.modified_at,
            "created_by": BasicUserSerializer(project.created_by).data,
            "modified_by": BasicUserSerializer(project.modified_by).data,
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


def get_proxy_for_display(proxy: str) -> str:
    if not (proxy.startswith("http://") or proxy.startswith("https://")):
        return proxy
    result = urlparse(proxy)
    if "@" not in proxy:
        return proxy
    cred, domain = result.netloc.split("@")
    if ":" in cred:
        user, _ = cred.split(":")
        domain = f"{user}:{ENCRYPTED_STRING}@{domain}"
    else:
        domain = f"{ENCRYPTED_STRING}@{domain}"

    unparsed = (
        result.scheme,
        domain,
        result.path,
        result.params,
        result.query,
        result.fragment,
    )
    return urlunparse(unparsed)
