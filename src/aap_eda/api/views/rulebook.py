import yaml
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from aap_eda.api import serializers
from aap_eda.api.services import RulebookService
from aap_eda.core import models


@extend_schema_view(
    retrieve=extend_schema(
        description="Get the rulebook by its id",
        responses={
            200: OpenApiResponse(
                serializers.RulebookSerializer,
                description=("Return the rulebook by its id."),
            ),
        },
    ),
    list=extend_schema(
        description="List all rulebooks",
        responses={
            200: OpenApiResponse(
                serializers.RulebookSerializer,
                description=("Return a list of rulebooks."),
            ),
        },
    ),
    create=extend_schema(
        description="Create a rulebook",
        responses={
            201: OpenApiResponse(
                serializers.RulebookSerializer,
                description=("Return the created rulebook."),
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
    http_method_names = ["get", "post"]

    @extend_schema(
        description=("Ruleset list of a rulebook by its id"),
        request=None,
        responses={200: serializers.RulesetOutSerializer(many=True)},
    )
    @action(detail=True)
    def rulesets(self, request, pk):
        rulebook = get_object_or_404(models.Rulebook, pk=pk)
        rulesets = models.Ruleset.objects.filter(rulebook=rulebook)

        result = []
        for ruleset in rulesets:
            data = model_to_dict(ruleset)

            data["source_types"] = [
                src["type"] for src in (data["sources"] or [])
            ]
            data["rule_count"] = models.Rule.objects.filter(
                ruleset_id=ruleset.id
            ).count()
            data["fired_stats"] = RulebookService(rulebook).build_fired_stat(
                data
            )

            for key in ["rulebook", "sources"]:
                data.pop(key)

            result.append(data)

        return Response(result)

    @extend_schema(
        description=("Get the JSON format of a rulebook by its id"),
        request=None,
        responses={200: serializers.RulebookSerializer(many=False)},
    )
    @action(detail=True)
    def json(self, request, pk):
        rulebook = get_object_or_404(models.Rulebook, pk=pk)
        data = model_to_dict(rulebook)
        data["rulesets"] = yaml.safe_load(data["rulesets"])

        return JsonResponse(data)
