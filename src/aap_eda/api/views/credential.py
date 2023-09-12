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

from cryptography import fernet
from django_filters import rest_framework as defaultfilters
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from aap_eda.api import filters, serializers
from aap_eda.core import models

from .mixins import (
    CreateModelMixin,
    PartialUpdateOnlyModelMixin,
    ResponseSerializerMixin,
)

logger = logging.getLogger(__name__)


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
    create=extend_schema(
        description="Create a new credential.",
        request=serializers.CredentialCreateSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.CredentialSerializer,
                description="Return the new credential.",
            ),
        },
    ),
    partial_update=extend_schema(
        description="Partial update of a credential",
        request=serializers.CredentialCreateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.CredentialSerializer,
                description="Update successful. Return an updated credential.",
            )
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
class CredentialViewSet(
    ResponseSerializerMixin,
    CreateModelMixin,
    PartialUpdateOnlyModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.Credential.objects.order_by("id")
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.CredentialFilter

    def handle_exception(self, exc):
        if isinstance(exc, fernet.InvalidToken):
            return Response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                data={
                    "details": (
                        "Credential decryption failed"
                        "; contact your system administrator"
                    )
                },
            )
        return super().handle_exception(exc)

    def get_serializer_class(self):
        if self.action in ["create", "partial_update"]:
            return serializers.CredentialCreateSerializer
        return serializers.CredentialSerializer

    def get_response_serializer_class(self):
        return serializers.CredentialSerializer
