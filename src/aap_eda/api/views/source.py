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

import logging

import yaml
from django.conf import settings
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as defaultfilters
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from aap_eda.api import filters, serializers
from aap_eda.core import models
from aap_eda.core.enums import ResourceType

logger = logging.getLogger(__name__)


class SourceViewSet(
    mixins.CreateModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.Source.objects.order_by("-created_at")
    serializer_class = serializers.SourceSerializer
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.SourceFilter
    rbac_resource_type = ResourceType.SOURCE

    @extend_schema(
        description="Get the Source by its id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.SourceOutSerializer,
                description="Return the source by its id.",
            ),
        },
    )
    def retrieve(self, request, pk: int):
        source = get_object_or_404(models.Source, pk=pk)
        return Response(serializers.SourceOutSerializer(source).data)

    @extend_schema(
        description="List all sources",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.SourceOutSerializer(many=True),
                description="Return a list of sources.",
            ),
        },
    )
    def list(self, request):
        sources = models.Source.objects.all()
        sources = self.filter_queryset(sources)

        serializer = serializers.SourceOutSerializer(sources, many=True)
        result = self.paginate_queryset(serializer.data)

        return self.get_paginated_response(result)

    @extend_schema(
        request=serializers.SourceSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.SourceOutSerializer,
                description="Return the new source.",
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Invalid data to create source."
            ),
        },
    )
    def create(self, request):
        context = {"request": request}

        # convert 'args' into yaml format
        in_args = request.data.get("args", {})
        request.data["args"] = yaml.dump(in_args)

        serializer = serializers.SourceSerializer(
            data=request.data,
            context=context,
        )
        serializer.is_valid(raise_exception=True)
        response = serializer.create(serializer.validated_data)

        # TODO: set listener_args
        if response.listener_args is None:
            listener_args = {
                "EDA_PG_NOTIFY_DSN": settings.PG_NOTIFY_DSN,
                "EDA_PG_NOTIFY_CHANNEL": str(response.uuid),
            }
            response.listener_args = yaml.dump(listener_args)
            response.save(update_fields=["listener_args"])

        return Response(
            serializers.SourceOutSerializer(response).data,
            status=status.HTTP_201_CREATED,
        )
