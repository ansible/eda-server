#  Copyright 2025 Red Hat, Inc.
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
"""
The CredentialInputSource is used to link to external SMS.

The Secret Management System provides the secrets which can
be retrieved at runtime.
"""

import logging

from ansible_base.rbac.api.related import check_related_permissions
from ansible_base.rbac.models import RoleDefinition
from django.db import transaction
from django.forms import model_to_dict
from django_filters import rest_framework as defaultfilters
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from aap_eda.api import filters, serializers
from aap_eda.api.serializers.eda_credential import get_references
from aap_eda.core import models
from aap_eda.core.enums import ResourceType
from aap_eda.core.utils.credentials import (
    inputs_to_store,
    inputs_to_store_dict,
)
from aap_eda.utils import str_to_bool

from .mixins import (
    CreateModelMixin,
    PartialUpdateOnlyModelMixin,
    ResponseSerializerMixin,
)

logger = logging.getLogger(__name__)


class CredentialInputSourceViewSet(
    ResponseSerializerMixin,
    CreateModelMixin,
    PartialUpdateOnlyModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    The CredentialInputSourceViewSet is used to link fields to external SMS.

    When the linkage happens we need the Source, Target credential and the
    field name
    """

    queryset = models.CredentialInputSource.objects.all()
    serializer_class = serializers.CredentialInputSourceSerializer
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.CredentialInputSourceFilter
    rbac_resource_type = ResourceType.CREDENTIAL_INPUT_SOURCE

    def filter_queryset(self, queryset):
        if queryset.model is models.CredentialInputSource:
            return super().filter_queryset(
                queryset.model.access_qs(self.request.user, queryset=queryset)
            )

    @extend_schema(
        description="Get CredentialInputSource by id",
        parameters=[
            OpenApiParameter(
                "refs",
                required=False,
                enum=["true", "false"],
                description=(
                    "Query resources that have reference to the "
                    "credential input source by its id"
                ),
            ),
        ],
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.CredentialInputSourceSerializer,
                description="Return an Credential Input Source by id.",
            ),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = serializers.CredentialInputSourceSerializer(obj)

        refs = str_to_bool(request.query_params.get("refs", "false"))

        serializer.references = get_references(obj) if refs else None

        return Response(serializer.data)

    @extend_schema(
        description="Create a new Credential Input Source.",
        request=serializers.CredentialInputSourceCreateSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.CredentialInputSourceSerializer,
                description="Return the new Credential Input Source.",
            ),
        },
    )
    def create(self, request, *args, **kwargs):
        return self._create_credential_input_source(request, request.data)

    @extend_schema(
        description="List all Credential Input Sources",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.CredentialInputSourceSerializer(many=True),
                description="Return a list of Credential Input Sources.",
            ),
        },
    )
    def list(self, request, *args, **kwargs):
        objects = self.get_queryset()
        objects = self.filter_queryset(objects)

        serializer = serializers.CredentialInputSourceSerializer(
            objects, many=True
        )
        result = self.paginate_queryset(serializer.data)

        return self.get_paginated_response(result)

    @extend_schema(
        description="Partial update of an Credential Input Source",
        request=serializers.CredentialInputSourceUpdateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.CredentialInputSourceSerializer,
                description=(
                    "Update successful. Return an updated "
                    "credential input source."
                ),
            )
        },
    )
    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        data = request.data

        data["metadata"] = inputs_to_store_dict(
            data.get("metadata", {}), obj.metadata
        )

        serializer = serializers.CredentialInputSourceUpdateSerializer(
            obj, data=data, partial=True
        )
        serializer.is_valid(raise_exception=True)

        metadata = serializer.validated_data.get("metadata")
        if metadata or metadata == {}:
            serializer.validated_data["metadata"] = inputs_to_store(
                metadata,
                obj.metadata,
            )

        old_data = model_to_dict(obj)
        for key, value in serializer.validated_data.items():
            setattr(obj, key, value)

        with transaction.atomic():
            obj.save()
            check_related_permissions(
                request.user,
                serializer.Meta.model,
                old_data,
                model_to_dict(obj),
            )

        obj.refresh_from_db()
        return Response(
            serializers.CredentialInputSourceSerializer(obj).data,
        )

    def _create_credential_input_source(self, request, data):
        """Create a new credential input source given payload data."""
        serializer = serializers.CredentialInputSourceCreateSerializer(
            data=data
        )
        serializer.is_valid(raise_exception=True)
        serializer.validated_data["metadata"] = inputs_to_store(
            serializer.validated_data["metadata"]
        )
        with transaction.atomic():
            response = serializer.create(serializer.validated_data)
            check_related_permissions(
                request.user,
                serializer.Meta.model,
                {},
                model_to_dict(response),
            )
            RoleDefinition.objects.give_creator_permissions(
                request.user, response
            )

        return Response(
            serializers.CredentialInputSourceSerializer(response).data,
            status=status.HTTP_201_CREATED,
        )
