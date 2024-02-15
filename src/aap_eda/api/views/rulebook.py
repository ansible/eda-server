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

import yaml
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as defaultfilters
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter

from aap_eda.api import filters, serializers
from aap_eda.core import models
from aap_eda.core.enums import Action, ResourceType


@extend_schema_view(
    retrieve=extend_schema(
        description="Get the rulebook by its id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.RulebookSerializer,
                description="Return the rulebook by its id.",
            ),
        },
    ),
    list=extend_schema(
        description="List all rulebooks",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.RulebookSerializer,
                description="Return a list of rulebooks.",
            ),
        },
    ),
)
class RulebookViewSet(
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.Rulebook.objects.order_by("id")
    serializer_class = serializers.RulebookSerializer
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.RulebookFilter

    rbac_action = None

    @extend_schema(
        description="Get the JSON format of a rulebook by its id",
        request=None,
        responses={status.HTTP_200_OK: serializers.RulebookSerializer},
    )
    @action(detail=True, rbac_action=Action.READ)
    def json(self, request, pk):
        rulebook = get_object_or_404(models.Rulebook, pk=pk)
        data = serializers.RulebookSerializer(rulebook).data
        data["rulesets"] = yaml.safe_load(data["rulesets"])

        return JsonResponse(data)


@extend_schema_view(
    retrieve=extend_schema(
        description="Get the fired rule by its id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.AuditRuleDetailSerializer,
                description="Return the fired rule by its id.",
            ),
        },
    ),
    list=extend_schema(
        description="List all fired rules",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.AuditRuleListSerializer,
                description="Return a list of fired rules.",
            ),
        },
    ),
)
class AuditRuleViewSet(
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.AuditRule.objects.all()
    filter_backends = (defaultfilters.DjangoFilterBackend, OrderingFilter)
    filterset_class = filters.AuditRuleFilter
    ordering_fields = [
        "id",
        "name",
        "status",
        "activation_instance__name",
        "fired_at",
    ]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers.AuditRuleDetailSerializer
        elif self.action == "list":
            return serializers.AuditRuleListSerializer
        elif self.action == "actions":
            return serializers.AuditActionSerializer
        elif self.action == "events":
            return serializers.AuditEventSerializer
        return serializers.AuditRuleSerializer

    rbac_resource_type = ResourceType.AUDIT_RULE
    rbac_action = None

    @extend_schema(
        description="Action list of a fired rule by its id",
        request=None,
        responses={
            status.HTTP_200_OK: serializers.AuditActionSerializer(many=True)
        },
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="A unique integer value identifying this rule audit.",  # noqa: E501
            )
        ],
    )
    @action(
        detail=False,
        queryset=models.AuditAction.objects.order_by("id"),
        filterset_class=filters.AuditRuleActionFilter,
        ordering_fields=[
            "name",
            "status",
            "url",
            "fired_at",
        ],
        rbac_action=Action.READ,
        url_path="(?P<id>[^/.]+)/actions",
    )
    def actions(self, _request, id):
        audit_rule = get_object_or_404(models.AuditRule, id=id)
        audit_actions = models.AuditAction.objects.filter(
            audit_rule=audit_rule,
            rule_fired_at=audit_rule.fired_at,
        )
        audit_actions = self.filter_queryset(audit_actions)

        results = self.paginate_queryset(audit_actions)
        serializer = serializers.AuditActionSerializer(results, many=True)

        return self.get_paginated_response(serializer.data)

    @extend_schema(
        description="Event list of a fired rule by its id",
        request=None,
        responses={
            status.HTTP_200_OK: serializers.AuditEventSerializer(many=True)
        },
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="A unique integer value identifying this Audit Rule.",  # noqa: E501
            )
        ],
    )
    @action(
        detail=False,
        queryset=models.AuditEvent.objects.order_by("-received_at"),
        filterset_class=filters.AuditRuleEventFilter,
        ordering_fields=[
            "source_name",
            "source_type",
            "received_at",
        ],
        rbac_resource_type=ResourceType.AUDIT_EVENT,
        rbac_action=Action.READ,
        url_path="(?P<id>[^/.]+)/events",
    )
    def events(self, _request, id):
        audit_rule = get_object_or_404(models.AuditRule, id=id)
        audit_actions = models.AuditAction.objects.filter(
            audit_rule=audit_rule,
            rule_fired_at=audit_rule.fired_at,
        )

        audit_events = models.AuditEvent.objects.none()
        for audit_action in audit_actions:
            audit_events |= audit_action.audit_events.all()

        filtered_audit_events = self.filter_queryset(audit_events.distinct())

        results = self.paginate_queryset(filtered_audit_events)
        serializer = serializers.AuditEventSerializer(results, many=True)

        return self.get_paginated_response(serializer.data)
