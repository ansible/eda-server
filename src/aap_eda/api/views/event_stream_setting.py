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
"""EventStreamSetting API — per-org IP security settings."""

import logging

from django_filters import rest_framework as defaultfilters
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from aap_eda.api import filters, serializers
from aap_eda.api.views.mixins import (
    CreateModelMixin,
    PartialUpdateOnlyModelMixin,
    ResponseSerializerMixin,
)
from aap_eda.core import models
from aap_eda.core.enums import ResourceType
from aap_eda.services.event_stream_settings_cache import (
    invalidate_org_settings,
)

logger = logging.getLogger(__name__)


class EventStreamSettingViewSet(
    ResponseSerializerMixin,
    CreateModelMixin,
    PartialUpdateOnlyModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.EventStreamSetting.objects.order_by("-created_at")
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.EventStreamSettingFilter
    rbac_resource_type = ResourceType.EVENT_STREAM_SETTING

    def get_serializer_class(self):
        if self.action in ("create", "partial_update"):
            return serializers.EventStreamSettingCreateSerializer
        return serializers.EventStreamSettingOutSerializer

    def get_response_serializer_class(self):
        return serializers.EventStreamSettingOutSerializer

    def filter_queryset(self, queryset):
        return super().filter_queryset(
            queryset.model.access_qs(self.request.user, queryset=queryset)
        )

    @extend_schema(
        description="Get event stream settings by id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EventStreamSettingOutSerializer,
                description=("Return the event stream settings."),
            ),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        description="List event stream settings",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EventStreamSettingOutSerializer(many=True),
                description=("Return a list of event stream settings."),
            ),
        },
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=serializers.EventStreamSettingCreateSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.EventStreamSettingOutSerializer,
                description=("Return the new event stream settings."),
            ),
        },
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        request=serializers.EventStreamSettingCreateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EventStreamSettingOutSerializer,
                description=("Return the updated event stream settings."),
            ),
        },
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        description=("Remove specific IPs from the blocked list."),
        request=serializers.RemoveBlockedIpsSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EventStreamSettingOutSerializer,
                description=("Return the updated event stream settings."),
            ),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="remove-blocked",
    )
    def remove_blocked(self, request, pk=None):
        """Remove specific IPs from the blocked list."""
        setting = self.get_object()
        sz = serializers.RemoveBlockedIpsSerializer(data=request.data)
        sz.is_valid(raise_exception=True)
        ips_to_remove = set(sz.validated_data["ips"])

        setting.blocked_ips = [
            ip for ip in setting.blocked_ips if ip not in ips_to_remove
        ]
        setting.save(update_fields=["blocked_ips", "modified_at"])
        invalidate_org_settings(setting.organization_id)

        logger.info(
            "Removed %d IPs from blocked list for org %s",
            len(ips_to_remove),
            setting.organization_id,
        )
        return Response(
            serializers.EventStreamSettingOutSerializer(setting).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        description="Clear all IPs from the blocked list.",
        request=None,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EventStreamSettingOutSerializer,
                description=("Return the updated event stream settings."),
            ),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="clear-blocked",
    )
    def clear_blocked(self, request, pk=None):
        """Clear all blocked IPs."""
        setting = self.get_object()
        setting.blocked_ips = []
        setting.save(update_fields=["blocked_ips", "modified_at"])
        invalidate_org_settings(setting.organization_id)

        logger.info(
            "Cleared all blocked IPs for org %s",
            setting.organization_id,
        )
        return Response(
            serializers.EventStreamSettingOutSerializer(setting).data,
            status=status.HTTP_200_OK,
        )
