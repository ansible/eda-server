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
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from aap_eda.api import exceptions, filters, serializers
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
        parameters=[
            OpenApiParameter(
                name="force",
                description="Force deletion if there are dependent objects",
                required=False,
                type=bool,
            )
        ],
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

    def destroy(self, request, *args, **kwargs):
        force = request.query_params.get("force", "false").lower() in [
            "true",
            "1",
            "yes",
        ]
        credential = self.get_object()

        # If the credential is in use and the 'force' flag
        # is not True, raise a PermissionDenied exception
        is_used = models.Activation.objects.filter(
            decision_environment__credential=credential
        ).exists()

        if is_used and not force:
            raise exceptions.Conflict(
                "Credential is being used by Activations "
                "and cannot be deleted. If you want to force delete, "
                "please add /?force=true query param."
            )
        self.perform_destroy(credential)
        return Response(status=status.HTTP_204_NO_CONTENT)
