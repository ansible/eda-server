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
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from aap_eda.api import filters, serializers
from aap_eda.core import models
from aap_eda.core.enums import Action, ResourceType
from aap_eda.services.rulebook import build_fired_stats, build_ruleset_out_data


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
        description="Ruleset list of a rulebook by its id",
        request=None,
        responses={
            status.HTTP_200_OK: serializers.RulesetOutSerializer(many=True)
        },
    )
    @action(
        detail=True,
        queryset=models.Ruleset.objects.order_by("id"),
        filterset_class=filters.RulesetFilter,
        rbac_action=Action.READ,
    )
    def rulesets(self, request, pk):
        rulebook = get_object_or_404(models.Rulebook, pk=pk)
        rulesets = models.Ruleset.objects.filter(rulebook=rulebook)

        rulesets = self.filter_queryset(rulesets)

        result = []
        for ruleset in rulesets:
            ruleset_data = serializers.RulesetSerializer(ruleset).data
            data = build_ruleset_out_data(ruleset_data)
            result.append(data)

        result = self.paginate_queryset(result)

        return self.get_paginated_response(result)

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


class RulesetViewSet(
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.Ruleset.objects.order_by("id")
    serializer_class = serializers.RulesetSerializer
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.RulesetFilter

    rbac_action = None
    rbac_resource_type = ResourceType.RULEBOOK

    @extend_schema(
        description="Get the ruleset by its id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.RulesetOutSerializer,
                description="Return the ruleset by its id.",
            ),
        },
    )
    def retrieve(self, request, pk=None):
        ruleset = get_object_or_404(models.Ruleset, pk=pk)
        ruleset_data = serializers.RulesetSerializer(ruleset).data
        data = build_ruleset_out_data(ruleset_data)

        return Response(data)

    @extend_schema(
        description="List all rulesets",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.RulesetOutSerializer(many=True),
                description="Return a list of rulesets.",
            ),
        },
    )
    def list(self, _request):
        rulesets = models.Ruleset.objects.all()
        rulesets = self.filter_queryset(rulesets)

        result = []
        for ruleset in rulesets:
            ruleset_data = serializers.RulesetSerializer(ruleset).data
            data = build_ruleset_out_data(ruleset_data)
            result.append(data)

        result = self.paginate_queryset(result)

        return self.get_paginated_response(result)

    @extend_schema(
        description="Rule list of a ruleset by its id",
        request=None,
        responses={status.HTTP_200_OK: serializers.RuleSerializer(many=True)},
    )
    @action(detail=True, rbac_action=Action.READ)
    def rules(self, _request, pk):
        ruleset = get_object_or_404(models.Ruleset, pk=pk)
        rules = models.Rule.objects.filter(ruleset=ruleset).order_by("id")

        results = self.paginate_queryset(rules)
        serializer = serializers.RuleSerializer(results, many=True)

        return self.get_paginated_response(serializer.data)


class AuditRuleViewSet(
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.AuditRule.objects.all()
    serializer_class = serializers.AuditRuleSerializer
    rbac_resource_type = ResourceType.AUDIT_RULE
    rbac_action = None

    @extend_schema(
        description="Get the fired rule by its id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.AuditRuleOutSerializer,
                description="Return the fired rule by its id.",
            ),
        },
    )
    def retrieve(self, _request, pk=None):
        audit_rule = get_object_or_404(models.AuditRule, pk=pk)
        activation = audit_rule.activation_instance.activation

        data = serializers.AuditRuleSerializer(audit_rule).data
        data["activation_id"] = activation.id
        data["activation_name"] = activation.name

        return Response(data)

    @extend_schema(
        description="List all fired rules",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.AuditRuleSerializer,
                description="Return a list of fired rules.",
            ),
        },
    )
    def list(self, _request):
        audit_rules = models.AuditRule.objects.all()
        results = self.filter_queryset(audit_rules)

        results = self.paginate_queryset(results)
        serializer = serializers.AuditRuleSerializer(results, many=True)

        return self.get_paginated_response(serializer.data)

    @extend_schema(
        description="Action list of a fired rule by its id",
        request=None,
        responses={
            status.HTTP_200_OK: serializers.AuditActionSerializer(many=True)
        },
    )
    @action(detail=True, rbac_action=Action.READ)
    def actions(self, _request, pk):
        audit_rule = get_object_or_404(models.AuditRule, pk=pk)
        audit_actions = models.AuditAction.objects.filter(
            audit_rule=audit_rule,
            rule_fired_at=audit_rule.fired_at,
        )

        results = self.paginate_queryset(audit_actions)
        serializer = serializers.AuditActionSerializer(results, many=True)

        return self.get_paginated_response(serializer.data)

    @extend_schema(
        description="Event list of a fired rule by its id",
        request=None,
        responses={
            status.HTTP_200_OK: serializers.AuditEventSerializer(many=True)
        },
    )
    @action(
        detail=True,
        rbac_resource_type=ResourceType.AUDIT_EVENT,
        rbac_action=Action.READ,
    )
    def events(self, _request, pk):
        audit_rule = get_object_or_404(models.AuditRule, pk=pk)
        audit_actions = models.AuditAction.objects.filter(
            audit_rule=audit_rule,
            rule_fired_at=audit_rule.fired_at,
        )

        eqs = models.AuditEvent.objects.none()
        for audit_action in audit_actions:
            eqs = eqs.union(audit_action.audit_events.all())

        results = self.paginate_queryset(eqs)
        serializer = serializers.AuditEventSerializer(results, many=True)

        return self.get_paginated_response(serializer.data)


@extend_schema_view(
    retrieve=extend_schema(
        description="Get the audit event by its id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.AuditEventSerializer,
                description="Return the audit event by its id.",
            ),
        },
    ),
    list=extend_schema(
        description="List all audit events",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.AuditEventSerializer,
                description="Return a list of audit events.",
            ),
        },
    ),
)
class AuditEventViewSet(
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.AuditEvent.objects.all()
    serializer_class = serializers.AuditEventSerializer

    rbac_resource_type = ResourceType.AUDIT_EVENT


class RuleViewSet(
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.Rule.objects.order_by("id")
    serializer_class = serializers.RuleSerializer

    rbac_resource_type = ResourceType.RULEBOOK

    @extend_schema(
        description="Get the rule by its id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.RuleOutSerializer(many=False),
                description="Return the rule by its id.",
            ),
        },
    )
    def retrieve(self, _request, pk=None):
        rule = get_object_or_404(models.Rule, pk=pk)
        data = self._build_rule_out_data(rule)

        return Response(data)

    @extend_schema(
        description="List all rules",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.RuleOutSerializer(many=True),
                description="Return a list of rules.",
            ),
        },
    )
    def list(self, _request):
        rules = models.Rule.objects.order_by("id")

        result = []
        for rule in rules:
            data = self._build_rule_out_data(rule)
            result.append(data)

        result = self.paginate_queryset(result)

        return self.get_paginated_response(result)

    def _build_rule_out_data(self, rule: models.Rule) -> dict:
        data = serializers.RuleSerializer(rule).data

        ruleset = models.Ruleset.objects.get(id=rule.ruleset_id)
        rulebook = models.Rulebook.objects.get(id=ruleset.rulebook_id)
        project = models.Project.objects.get(id=rulebook.project_id)

        data["fired_stats"] = build_fired_stats(data)
        data["rulebook"] = rulebook.id
        data["project"] = project.id

        return data
