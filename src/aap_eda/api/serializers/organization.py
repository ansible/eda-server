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

from aap_eda.core.models import Organization

from .fields.ansible_resource import AnsibleResourceFieldSerializer


class OrganizationSerializer(NamedCommonModelSerializer):
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
