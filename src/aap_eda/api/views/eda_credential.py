#  Copyright 2024 Red Hat, Inc.
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
from aap_eda.api.serializers.utils import inputs_to_store
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
        description="Get EDA credential by id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EdaCredentialSerializer,
                description="Return an EDA credential by id.",
            ),
        },
    ),
    list=extend_schema(
        description="List all EDA credentials",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EdaCredentialSerializer(many=True),
                description="Return a list of EDA credentials.",
            ),
        },
    ),
    destroy=extend_schema(
        description="Delete an EDA credential by id",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None, description="Delete successful."
            )
        },
    ),
)
class EdaCredentialViewSet(
    ResponseSerializerMixin,
    CreateModelMixin,
    PartialUpdateOnlyModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.EdaCredential.objects.all()
    serializer_class = serializers.EdaCredentialSerializer
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.EdaCredentialFilter

    rbac_resource_type = ResourceType.EDA_CREDENTIAL
    rbac_action = None

    @extend_schema(
        description="Create a new EDA credential.",
        request=serializers.EdaCredentialCreateSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.EdaCredentialSerializer,
                description="Return the new EDA credential.",
            ),
        },
    )
    def create(self, request):
        serializer = serializers.EdaCredentialCreateSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)
        serializer.validated_data["inputs"] = inputs_to_store(
            serializer.validated_data["inputs"]
        )
        eda_credential = serializer.create(serializer.validated_data)

        return Response(
            serializers.EdaCredentialSerializer(eda_credential).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        description="Partial update of an EDA credential",
        request=serializers.EdaCredentialUpdateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EdaCredentialSerializer,
                description=(
                    "Update successful. Return an updated EDA credential."
                ),
            )
        },
    )
    def partial_update(self, request, pk):
        eda_credential = self.get_object()
        serializer = serializers.EdaCredentialUpdateSerializer(
            eda_credential, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data.get("inputs"):
            serializer.validated_data["inputs"] = inputs_to_store(
                serializer.validated_data["inputs"],
                eda_credential.inputs,
            )

        for key, value in serializer.validated_data.items():
            setattr(eda_credential, key, value)

        eda_credential.save()

        return Response(
            serializers.EdaCredentialSerializer(eda_credential).data,
            status=status.HTTP_206_PARTIAL_CONTENT,
        )
