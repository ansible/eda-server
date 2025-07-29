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
import uuid
from typing import Optional
from urllib.parse import urljoin

import yaml
from django.conf import settings
from django.urls import reverse
from rest_framework import serializers

from aap_eda.api.serializers.eda_credential import EdaCredentialRefSerializer
from aap_eda.api.serializers.fields.basic_user import BasicUserFieldSerializer
from aap_eda.api.serializers.organization import OrganizationRefSerializer
from aap_eda.api.serializers.user import BasicUserSerializer
from aap_eda.core import enums, models, validators


class EventStreamInSerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(
        required=True,
        allow_null=False,
        error_messages={"null": "Organization is needed"},
    )
    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())
    eda_credential_id = serializers.IntegerField(
        required=True,
        allow_null=False,
        validators=[
            validators.check_credential_types_for_event_stream,
        ],
        error_messages={"null": "EdaCredential is needed"},
    )
    uuid = serializers.UUIDField(required=False, allow_null=True)

    def validate_uuid(self, value):
        if value is None:
            return uuid.uuid4()

        # Check uniqueness for provided UUID
        queryset = models.EventStream.objects.filter(uuid=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "Event stream with this UUID already exists."
            )
        return value

    def validate(self, data):
        eda_credential_id = data.get("eda_credential_id")

        credential = (
            models.EdaCredential.objects.get(id=eda_credential_id)
            if eda_credential_id
            else self.instance.eda_credential
        )

        kind = credential.credential_type.kind

        event_stream_type = data.get("event_stream_type")
        if event_stream_type and kind != event_stream_type:
            raise serializers.ValidationError(
                f"The input event stream type {event_stream_type} does not "
                f"match with the credential type {kind}"
            )

        if not event_stream_type:
            data["event_stream_type"] = kind

        return data

    class Meta:
        model = models.EventStream
        fields = [
            "name",
            "owner",
            "test_mode",
            "additional_data_headers",
            "eda_credential_id",
            "organization_id",
            "uuid",
        ]


class EventStreamOutSerializer(serializers.ModelSerializer):
    owner = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()
    eda_credential = EdaCredentialRefSerializer(
        required=True, allow_null=False
    )
    url = serializers.SerializerMethodField()
    created_by = BasicUserFieldSerializer()
    modified_by = BasicUserFieldSerializer()

    class Meta:
        model = models.EventStream
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
            "event_stream_type",
            "uuid",
            "created_by",
            "modified_by",
            *read_only_fields,
        ]

    def get_url(self, obj) -> str:
        path = reverse(
            "external_event_stream-post",
            kwargs={"pk": obj.uuid},
        ).lstrip("/")
        inputs = yaml.safe_load(obj.eda_credential.inputs.get_secret_value())
        if inputs.get("auth_type", None) == enums.EventStreamAuthType.MTLS:
            return urljoin(settings.EVENT_STREAM_MTLS_BASE_URL, path)
        return urljoin(settings.EVENT_STREAM_BASE_URL, path)

    def get_owner(self, obj) -> str:
        if obj.owner:
            return f"{obj.owner.username}"
        else:
            return ""

    def get_organization(self, obj) -> Optional[OrganizationRefSerializer]:
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
