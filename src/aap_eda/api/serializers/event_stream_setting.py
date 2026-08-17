#  Copyright 2026 Red Hat, Inc.
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

import ipaddress

from rest_framework import serializers

from aap_eda.api.serializers.fields.basic_user import BasicUserFieldSerializer
from aap_eda.api.serializers.organization import OrganizationRefSerializer
from aap_eda.api.serializers.user import BasicUserSerializer
from aap_eda.core import models, validators

MAX_IPS_PER_LIST = 255


def _validate_ip_list(value):
    if len(value) > MAX_IPS_PER_LIST:
        raise serializers.ValidationError(
            f"Maximum {MAX_IPS_PER_LIST} entries allowed."
        )
    from aap_eda.api.blacklist import normalize_ip

    normalized = []
    for entry in value:
        entry = entry.strip()
        if "/" in entry:
            try:
                net = ipaddress.ip_network(entry, strict=False)
                normalized.append(str(net))
            except ValueError:
                raise serializers.ValidationError(
                    f"'{entry}' is not a valid CIDR range."
                )
        else:
            try:
                ipaddress.ip_address(entry)
            except ValueError:
                raise serializers.ValidationError(
                    f"'{entry}' is not a valid IP address."
                )
            normalized.append(normalize_ip(entry))
    return normalized


class EventStreamSettingCreateSerializer(
    serializers.ModelSerializer,
):
    organization_id = serializers.IntegerField(
        required=True,
        allow_null=False,
        validators=[validators.check_if_organization_exists],
        error_messages={"null": "Organization is required."},
    )
    allowed_ips = serializers.ListField(
        child=serializers.CharField(max_length=45),
        required=False,
        default=list,
    )
    blocked_ips = serializers.ListField(
        child=serializers.CharField(max_length=45),
        required=False,
        default=list,
    )

    class Meta:
        model = models.EventStreamSetting
        fields = [
            "organization_id",
            "allowed_ips",
            "blocked_ips",
        ]

    def validate_organization_id(self, value):
        if (
            not self.instance
            and models.EventStreamSetting.objects.filter(
                organization_id=value
            ).exists()
        ):
            raise serializers.ValidationError(
                "Settings already exist for this organization."
            )
        return value

    def validate_allowed_ips(self, value):
        return _validate_ip_list(value)

    def validate_blocked_ips(self, value):
        return _validate_ip_list(value)

    def update(self, instance, validated_data):
        new_allowed = validated_data.get("allowed_ips")
        if new_allowed is not None:
            added_ips = set(new_allowed) - set(instance.allowed_ips)
            if added_ips and instance.blocked_ips:
                instance.blocked_ips = [
                    ip for ip in instance.blocked_ips if ip not in added_ips
                ]
        return super().update(instance, validated_data)


class EventStreamSettingOutSerializer(
    serializers.ModelSerializer,
):
    organization = serializers.SerializerMethodField()
    created_by = BasicUserFieldSerializer()
    modified_by = BasicUserFieldSerializer()

    class Meta:
        model = models.EventStreamSetting
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
        ]
        fields = [
            "organization",
            "allowed_ips",
            "blocked_ips",
            "created_by",
            "modified_by",
            *read_only_fields,
        ]

    def get_organization(self, obj):
        return (
            OrganizationRefSerializer(obj.organization).data
            if obj.organization
            else None
        )

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result["created_by"] = BasicUserSerializer(instance.created_by).data
        result["modified_by"] = BasicUserSerializer(instance.modified_by).data
        return result


class RemoveBlockedIpsSerializer(serializers.Serializer):
    ips = serializers.ListField(
        child=serializers.CharField(max_length=45),
        required=True,
        help_text="IPs to remove from the blocked list.",
    )

    def validate_ips(self, value):
        return _validate_ip_list(value)
