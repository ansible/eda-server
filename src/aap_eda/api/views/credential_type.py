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
from aap_eda.core.enums import ResourceType

from .mixins import (
    CreateModelMixin,
    PartialUpdateOnlyModelMixin,
    ResponseSerializerMixin,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    retrieve=extend_schema(
        description="Get credential type by id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.CredentialTypeSerializer,
                description="Return a credential type by id.",
            ),
        },
    ),
    list=extend_schema(
        description="List all credential types",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.CredentialTypeSerializer(many=True),
                description="Return a list of credential types.",
            ),
        },
    ),
)
class CredentialTypeViewSet(
    ResponseSerializerMixin,
    CreateModelMixin,
    PartialUpdateOnlyModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.CredentialType.objects.all()
    serializer_class = serializers.CredentialTypeSerializer
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.CredentialTypeFilter
    ordering_fields = ["name"]

    rbac_resource_type = ResourceType.CREDENTIAL_TYPE
    rbac_action = None

    @extend_schema(
        description="Create a new credential type.",
        request=serializers.CredentialTypeCreateSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.CredentialTypeSerializer,
                description="Return the new credential type.",
            ),
        },
    )
    def create(self, request):
        serializer = serializers.CredentialTypeCreateSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)
        serializer.validated_data["kind"] = "cloud"
        for field in serializer.validated_data["inputs"]["fields"]:
            if "type" not in field:
                field["type"] = "string"
        credential_type = serializer.create(serializer.validated_data)

        return Response(
            serializers.CredentialTypeSerializer(credential_type).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        description="Partial update of a credential type",
        request=serializers.CredentialTypeCreateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.CredentialTypeSerializer,
                description=(
                    "Update successful. Return an updated credential type."
                ),
            )
        },
    )
    def partial_update(self, request, pk):
        credential_type = self.get_object()

        if credential_type.managed:
            error = "Managed credential type cannot be updated"
            return Response(
                {"errors": error}, status=status.HTTP_400_BAD_REQUEST
            )

        if models.EdaCredential.objects.filter(
            credential_type=credential_type
        ).exists():
            inputs = request.data.get("inputs")
            injectors = request.data.get("injectors")
            if inputs or injectors:
                field = "inputs" if inputs else "injectors"
                error = (
                    f"Modifications to {field} are not allowed for credential "
                    "types that are in use"
                )
                return Response(
                    data={field: [error]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = serializers.CredentialTypeCreateSerializer(
            credential_type, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)

        for key, value in serializer.validated_data.items():
            setattr(credential_type, key, value)

        credential_type.save()

        return Response(
            serializers.CredentialTypeSerializer(credential_type).data
        )

    @extend_schema(
        description="Delete a credential type by id",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None, description="Delete successful."
            ),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                None, description="CredentialType in use by Credentials."
            ),
        },
    )
    def destroy(self, request, *args, **kwargs):
        credential_type = self.get_object()
        if credential_type.managed:
            error = "Managed credential type cannot be deleted"
            return Response(
                {"errors": error}, status=status.HTTP_400_BAD_REQUEST
            )

        if models.EdaCredential.objects.filter(
            credential_type=credential_type
        ).exists():
            error = (
                f"CredentialType {credential_type.name} is used by credentials"
            )
            return Response({"errors": error}, status=status.HTTP_409_CONFLICT)

        self.perform_destroy(credential_type)
        return Response(status=status.HTTP_204_NO_CONTENT)
