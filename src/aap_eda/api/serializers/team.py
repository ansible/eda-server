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

from aap_eda.api.serializers.organization import OrganizationRefSerializer
from aap_eda.core import models, validators

from .fields.ansible_resource import AnsibleResourceFieldSerializer
from .mixins import SharedResourceSerializerMixin


class TeamSerializer(serializers.ModelSerializer):
    resource = AnsibleResourceFieldSerializer(read_only=True)

    class Meta:
        model = models.Team
        fields = [
            "id",
            "name",
            "description",
            "organization_id",
            "resource",
            "created",
            "created_by",
            "modified",
            "modified_by",
        ]


class TeamCreateSerializer(
    serializers.ModelSerializer,
    SharedResourceSerializerMixin,
):
    organization_id = serializers.IntegerField(
        required=True,
        allow_null=False,
        validators=[validators.check_if_organization_exists],
        error_messages={"null": "Organization is needed"},
    )

    class Meta:
        model = models.Team
        fields = [
            "name",
            "description",
            "organization_id",
        ]

    def validate(self, data):
        self.validate_shared_resource()
        return data


class TeamDetailSerializer(serializers.ModelSerializer):
    organization = OrganizationRefSerializer()
    resource = AnsibleResourceFieldSerializer(read_only=True)

    class Meta:
        model = models.Team
        fields = [
            "id",
            "name",
            "description",
            "organization",
            "resource",
            "created",
            "created_by",
            "modified",
            "modified_by",
        ]


class TeamUpdateSerializer(
    serializers.ModelSerializer,
    SharedResourceSerializerMixin,
):
    class Meta:
        model = models.Team
        fields = [
            "name",
            "description",
        ]

    def validate(self, data):
        self.validate_shared_resource()
        return data
