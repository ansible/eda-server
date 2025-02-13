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
from rest_framework.response import Response

from aap_eda.api import exceptions as api_exc, filters, serializers
from aap_eda.core import models
from aap_eda.core.enums import Action
from aap_eda.core.exceptions import ParseError
from aap_eda.core.utils.rulebook import build_source_list
from aap_eda.utils.openapi import generate_query_params


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

    def filter_queryset(self, queryset):
        return super().filter_queryset(
            queryset.model.access_qs(self.request.user, queryset=queryset)
        )

    @extend_schema(
        description="Get the JSON format of a rulebook by its id",
        request=None,
        responses={status.HTTP_200_OK: serializers.RulebookSerializer},
    )
    @action(detail=True)
    def json(self, request, pk):
        rulebook = self.get_object()
        data = serializers.RulebookSerializer(rulebook).data
        data["rulesets"] = yaml.safe_load(data["rulesets"])

        return JsonResponse(data)

    @extend_schema(
        description="Source list of a rulebook by its id",
        request=None,
        responses={
            status.HTTP_200_OK: serializers.SourceSerializer(many=True),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                None,
                description="Rulebook not parseable.",
            ),
        },
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="A unique integer value identifying this rulebook.",  # noqa: E501
            )
        ],
    )
    @action(
        detail=False,
        rbac_action=Action.READ,
        url_path="(?P<id>[^/.]+)/sources",
    )
    def sources(self, request, id):
        if not models.Rulebook.access_qs(request.user).filter(id=id).exists():
            raise api_exc.NotFound(
                code=status.HTTP_404_NOT_FOUND,
                detail=f"Rulebook with ID={id} does not exist.",
            )

        rulebook = models.Rulebook.objects.get(id=id)

        try:
            results = build_source_list(rulebook.rulesets)
        except ParseError as e:
            return Response(
                {"errors": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

        results = self.paginate_queryset(results)
        serializer = serializers.SourceSerializer(results, many=True)

        return self.get_paginated_response(serializer.data)


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
        parameters=generate_query_params(serializers.AuditRuleSerializer()),
    ),
)
class AuditRuleViewSet(
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.AuditRule.objects.all()

    def filter_queryset(self, queryset):
        if queryset.model is models.AuditRule:
            return super().filter_queryset(
                queryset.model.access_qs(self.request.user, queryset=queryset)
            )
        return super().filter_queryset(queryset)

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
            ),
        ]
        + generate_query_params(
            serializers.AuditActionSerializer(),
        ),
    )
    @action(
        detail=False,
        queryset=models.AuditAction.objects.order_by("id"),
        rbac_action=Action.READ,
        url_path="(?P<id>[^/.]+)/actions",
    )
    def actions(self, _request, id):
        audit_rule = get_object_or_404(
            models.AuditRule.access_qs(_request.user), id=id
        )
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
            ),
        ]
        + generate_query_params(serializers.AuditEventSerializer()),
    )
    @action(
        detail=False,
        queryset=models.AuditEvent.objects.order_by("-received_at"),
        rbac_action=Action.READ,
        url_path="(?P<id>[^/.]+)/events",
    )
    def events(self, _request, id):
        audit_rule = get_object_or_404(
            models.AuditRule.access_qs(_request.user), id=id
        )
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
