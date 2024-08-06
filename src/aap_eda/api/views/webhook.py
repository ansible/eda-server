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
"""Webhook configuration API Set."""
import logging
from urllib.parse import urljoin

import yaml
from ansible_base.rbac.api.related import check_related_permissions
from ansible_base.rbac.models import RoleDefinition
from django.conf import settings
from django.db import transaction
from django.forms import model_to_dict
from django_filters import rest_framework as defaultfilters
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from aap_eda.api import serializers
from aap_eda.api.filters.webhook import WebhookFilter
from aap_eda.core import models
from aap_eda.core.enums import ResourceType, WebhookAuthType

logger = logging.getLogger(__name__)

WEBHOOK_EXTERNAL_PATH = "api/eda/v1/external_webhook"


class WebhookViewSet(
    mixins.CreateModelMixin,
    viewsets.ReadOnlyModelViewSet,
    mixins.DestroyModelMixin,
):
    queryset = models.Webhook.objects.order_by("-created_at")
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = WebhookFilter
    rbac_resource_type = ResourceType.WEBHOOK

    def get_serializer_class(self):
        if self.action == "list":
            return serializers.WebhookOutSerializer
        if self.action == "destroy":
            return serializers.WebhookOutSerializer
        if self.action == "create":
            return serializers.WebhookInSerializer
        if self.action == "partial_update":
            return serializers.WebhookInSerializer

        return serializers.WebhookOutSerializer

    def get_response_serializer_class(self):
        return serializers.WebhookOutSerializer

    def filter_queryset(self, queryset):
        return super().filter_queryset(
            queryset.model.access_qs(self.request.user, queryset=queryset)
        )

    @extend_schema(
        description="Get the Webhook by its id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.WebhookOutSerializer,
                description="Return the webhook by its id.",
            ),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        webhook = self.get_object()
        return Response(serializers.WebhookOutSerializer(webhook).data)

    @extend_schema(
        description="Delete a Webhook by its id",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None, description="Delete successful."
            )
        },
    )
    def destroy(self, request, *args, **kwargs):
        webhook = self.get_object()
        self.perform_destroy(webhook)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description="List all webhooks",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.WebhookOutSerializer(many=True),
                description="Return a list of webhook.",
            ),
        },
    )
    def list(self, request, *args, **kwargs):
        webhooks = models.Webhook.objects.all()
        webhooks = self.filter_queryset(webhooks)
        serializer = serializers.WebhookOutSerializer(webhooks, many=True)
        result = self.paginate_queryset(serializer.data)

        return self.get_paginated_response(result)

    @extend_schema(
        request=serializers.WebhookInSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.WebhookOutSerializer,
                description="Return the new webhook.",
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Invalid data to create webhook."
            ),
        },
    )
    def create(self, request, *args, **kwargs):
        context = {"request": request}
        serializer = serializers.WebhookInSerializer(
            data=request.data,
            context=context,
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            response = serializer.save()
            check_related_permissions(
                request.user,
                serializer.Meta.model,
                {},
                model_to_dict(serializer.instance),
            )
            RoleDefinition.objects.give_creator_permissions(
                request.user, serializer.instance
            )
            inputs = yaml.safe_load(
                response.eda_credential.inputs.get_secret_value()
            )
            sub_path = f"{WEBHOOK_EXTERNAL_PATH}/{response.uuid}/post/"
            if inputs["auth_type"] == WebhookAuthType.MTLS:
                response.url = urljoin(
                    settings.WEBHOOK_MTLS_BASE_URL, sub_path
                )
            else:
                response.url = urljoin(settings.WEBHOOK_BASE_URL, sub_path)
            response.save(update_fields=["url"])

        return Response(
            serializers.WebhookOutSerializer(response).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=serializers.WebhookInSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.WebhookOutSerializer,
                description="Update successful, return the new webhook.",
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Unable to update webhook."
            ),
        },
    )
    def partial_update(self, request, *args, **kwargs):
        webhook = self.get_object()
        old_data = model_to_dict(webhook)
        context = {"request": request}
        serializer = serializers.WebhookInSerializer(
            webhook,
            data=request.data,
            context=context,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        if webhook.test_mode != request.data.get(
            "test_mode", webhook.test_mode
        ):
            webhook.test_content_type = ""
            webhook.test_content = ""
            webhook.test_headers = ""
            webhook.test_error_message = ""

        for key, value in serializer.validated_data.items():
            setattr(webhook, key, value)

        with transaction.atomic():
            webhook.save()
            check_related_permissions(
                request.user,
                serializer.Meta.model,
                old_data,
                model_to_dict(webhook),
            )

        return Response(
            serializers.WebhookOutSerializer(webhook).data,
            status=status.HTTP_200_OK,
        )
