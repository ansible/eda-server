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

from django.shortcuts import get_object_or_404
from django_filters import rest_framework as defaultfilters
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action

from aap_eda.api import filters, serializers
from aap_eda.core import models
from aap_eda.core.enums import Action, ResourceType

from .mixins import PartialUpdateOnlyModelMixin


@extend_schema_view(
    list=extend_schema(
        description="List all organizations.",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.OrganizationSerializer,
                description="Return a list of organizations.",
            ),
        },
    ),
    create=extend_schema(
        description="Create a new organization",
        request=serializers.OrganizationCreateSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.OrganizationSerializer,
                description="Return the new organization.",
            ),
        },
    ),
    partial_update=extend_schema(
        description="Partially update an organization",
        request=serializers.OrganizationCreateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.OrganizationSerializer,
                description="Update successful. Return an updated organization.",  # noqa: E501
            )
        },
    ),
)
class OrganizationViewSet(
    PartialUpdateOnlyModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.Organization.objects.order_by("id")
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.OrganizationFilter
    rbac_resource_type = ResourceType.ORGANIZATION
    rbac_action = None

    def get_serializer_class(self):
        return serializers.OrganizationSerializer

    def get_response_serializer_class(self):
        return serializers.OrganizationSerializer

    @extend_schema(
        description="List all teams of the organization",
        request=None,
        responses={
            status.HTTP_200_OK: serializers.TeamSerializer(many=True),
        },
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="A unique integer value identifying this organization.",  # noqa: E501
            )
        ],
    )
    @action(
        detail=False,
        queryset=models.Team.objects.order_by("id"),
        filterset_class=filters.OrganizationTeamFilter,
        rbac_resource_type=ResourceType.TEAM,
        rbac_action=Action.READ,
        url_path="(?P<id>[^/.]+)/teams",
    )
    def teams(self, request, id):
        organization = get_object_or_404(models.Organization, pk=id)

        teams = models.Team.objects.filter(organization_id=organization.id)
        filtered_teams = self.filter_queryset(teams)
        result = self.paginate_queryset(filtered_teams)
        serializer = serializers.TeamSerializer(result, many=True)
        return self.get_paginated_response(serializer.data)
