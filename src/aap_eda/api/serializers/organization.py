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

from ansible_base.lib.serializers.common import NamedCommonModelSerializer
from django.conf import settings

from aap_eda.api import exceptions as api_exc
from aap_eda.core.models import Organization

from .fields.ansible_resource import AnsibleResourceFieldSerializer
from .mixins import SharedResourceSerializerMixin


class OrganizationSerializer(
    NamedCommonModelSerializer,
    SharedResourceSerializerMixin,
):
    reverse_url_name = "organization-detail"

    resource = AnsibleResourceFieldSerializer(read_only=True)

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "description",
            "resource",
            "created",
            "created_by",
            "modified",
            "modified_by",
        ]

    def validate(self, data):
        self.validate_shared_resource()
        # when creating a new org, self.instance is empty
        if (
            self.instance
            and self.instance.name == settings.DEFAULT_ORGANIZATION_NAME
        ):
            raise api_exc.Conflict(
                "The default organization cannot be modified."
            )
        return data


class OrganizationRefSerializer(NamedCommonModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "description",
        ]


class OrganizationCreateSerializer(NamedCommonModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "name",
            "description",
        ]
