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

from django_filters import rest_framework as defaultfilters
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.response import Response

from aap_eda.api import filters, serializers
from aap_eda.core import models


@extend_schema_view(
    list=extend_schema(
        description="List all credentials",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.CredentialSerializer,
                description="Return a list of credential.",
            ),
        },
    ),
    retrieve=extend_schema(
        description="Get credential by id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.CredentialSerializer,
                description="Return a credential by id.",
            ),
        },
    ),
    destroy=extend_schema(
        description="Delete a credential by id",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None, description="Delete successful."
            )
        },
    ),
)
class CredentialViewSet(viewsets.ModelViewSet):
    queryset = models.Credential.objects.order_by("id")
    serializer_class = serializers.CredentialSerializer
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.CredentialFilter

    @extend_schema(
        description="Create a new credential.",
        request=serializers.CredentialCreateSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.CredentialSerializer,
                description="Return the new credential.",
            ),
        },
    )
    def create(self, request):
        serializer = serializers.CredentialCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        output_serializer = serializers.CredentialSerializer(serializer.save())
        return Response(
            status=status.HTTP_201_CREATED, data=output_serializer.data
        )

    @extend_schema(
        description="Update a credential",
        request=serializers.CredentialCreateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.CredentialSerializer,
                description="Update successful. Return an updated credential.",
            )
        },
    )
    def update(self, request, *args, **kwargs):
        instance = self.queryset.get(pk=kwargs.get("pk"))
        serializer = serializers.CredentialCreateSerializer(
            instance, data=request.data, partial=False
        )
        serializer.is_valid(raise_exception=True)
        output_serializer = serializers.CredentialSerializer(serializer.save())
        return Response(output_serializer.data)

    @extend_schema(
        description="Partial update of a credential",
        request=serializers.CredentialCreateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.CredentialSerializer,
                description="Update successful. Return an updated credential.",
            )
        },
    )
    def partial_update(self, request, *args, **kwargs):
        instance = self.queryset.get(pk=kwargs.get("pk"))
        serializer = serializers.CredentialCreateSerializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        output_serializer = serializers.CredentialSerializer(serializer.save())
        return Response(output_serializer.data)
