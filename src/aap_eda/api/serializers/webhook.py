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
from typing import Optional

from rest_framework import serializers

from aap_eda.api.serializers.eda_credential import EdaCredentialRefSerializer
from aap_eda.api.serializers.organization import OrganizationRefSerializer
from aap_eda.core import models, validators


class WebhookInSerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(required=True, allow_null=False)
    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())
    eda_credential_id = serializers.IntegerField(
        required=True,
        allow_null=False,
        validators=[
            validators.check_credential_types_for_webhook,
        ],
    )

    class Meta:
        model = models.Webhook
        fields = [
            "name",
            "owner",
            "test_mode",
            "additional_data_headers",
            "eda_credential_id",
            "organization_id",
            "webhook_type",
        ]


class WebhookOutSerializer(serializers.ModelSerializer):
    owner = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()
    eda_credential = EdaCredentialRefSerializer(
        required=True, allow_null=False
    )

    class Meta:
        model = models.Webhook
        read_only_fields = [
            "id",
            "owner",
            "url",
            "created_at",
            "modified_at",
            "test_content_type",
            "test_content",
            "test_error_message",
            "test_headers",
            "events_received",
            "last_event_received_at",
        ]
        fields = [
            "name",
            "test_mode",
            "additional_data_headers",
            "organization",
            "eda_credential",
            "webhook_type",
            *read_only_fields,
        ]

    def get_owner(self, obj) -> str:
        return f"{obj.owner.username}"

    def get_organization(self, obj) -> Optional[OrganizationRefSerializer]:
        return (
            OrganizationRefSerializer(obj.organization).data
            if obj.organization
            else None
        )
