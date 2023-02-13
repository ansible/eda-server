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
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from aap_eda.api import common, serializers
from aap_eda.api.services.rulebook import rule_out_data, ruleset_out_data
from aap_eda.core import models


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
    create=extend_schema(
        description="Create a rulebook",
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.RulebookSerializer,
                description="Return the created rulebook.",
            ),
        },
    ),
)
class RulebookViewSet(
    mixins.CreateModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.Rulebook.objects.all()
    serializer_class = serializers.RulebookSerializer
    pagination_class = common.StandardPagination

    @extend_schema(
        description="Ruleset list of a rulebook by its id",
        request=None,
        responses={
            status.HTTP_200_OK: serializers.RulesetOutSerializer(many=True)
        },
    )
    @action(detail=True)
    def rulesets(self, request, pk):
        rulebook = get_object_or_404(models.Rulebook, pk=pk)
        rulesets = models.Ruleset.objects.filter(rulebook=rulebook)

        result = []
        for ruleset in rulesets:
            data = ruleset_out_data(ruleset)
            result.append(data)

        result = self.paginate_queryset(result)

        return self.get_paginated_response(result)

    @extend_schema(
        description="Get the JSON format of a rulebook by its id",
        request=None,
        responses={status.HTTP_200_OK: serializers.RulebookSerializer},
    )
    @action(detail=True)
    def json(self, request, pk):
        rulebook = get_object_or_404(models.Rulebook, pk=pk)
        data = serializers.RulebookSerializer(rulebook).data
        data["rulesets"] = yaml.safe_load(data["rulesets"])

        return JsonResponse(data)


class RulesetViewSet(
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.Ruleset.objects.all()
    serializer_class = serializers.RulesetSerializer
    pagination_class = common.StandardPagination

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
        data = ruleset_out_data(ruleset)

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

        result = []
        for ruleset in rulesets:
            data = ruleset_out_data(ruleset)
            result.append(data)

        result = self.paginate_queryset(result)

        return self.get_paginated_response(result)

    @extend_schema(
        description="Rule list of a ruleset by its id",
        request=None,
        responses={status.HTTP_200_OK: serializers.RuleSerializer(many=True)},
    )
    @action(detail=True)
    def rules(self, _request, pk):
        ruleset = get_object_or_404(models.Ruleset, pk=pk)
        rules = models.Rule.objects.filter(ruleset=ruleset)

        results = self.paginate_queryset(rules)
        serializer = serializers.RuleSerializer(results, many=True)

        return self.get_paginated_response(serializer.data)


class RuleViewSet(
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.Rule.objects.all()
    serializer_class = serializers.RuleSerializer

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
        data = rule_out_data(rule)

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
        rules = models.Rule.objects.all()

        result = []
        for rule in rules:
            data = rule_out_data(rule)
            result.append(data)

        result = self.paginate_queryset(result)

        return self.get_paginated_response(result)
