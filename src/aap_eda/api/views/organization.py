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

from django.conf import settings
from django_filters import rest_framework as defaultfilters
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from aap_eda.api import exceptions as api_exc, filters, serializers
from aap_eda.core import models
from aap_eda.core.enums import Action

from .mixins import PartialUpdateOnlyModelMixin, SharedResourceViewMixin


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
        exclude=not settings.ALLOW_LOCAL_RESOURCE_MANAGEMENT,
        description="Create a new organization",
        request=serializers.OrganizationCreateSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.OrganizationSerializer,
                description="Return the new organization.",
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                None, description="Create is prohibited"
            ),
        },
    ),
    partial_update=extend_schema(
        exclude=not settings.ALLOW_LOCAL_RESOURCE_MANAGEMENT,
        description="Partially update an organization",
        request=serializers.OrganizationCreateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.OrganizationSerializer,
                description="Update successful. Return an updated organization.",  # noqa: E501
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                None, description="Update is prohibited"
            ),
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
    SharedResourceViewMixin,
):
    queryset = models.Organization.objects.order_by("id")
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.OrganizationFilter
    rbac_action = None

    def filter_queryset(self, queryset):
        return super().filter_queryset(
            queryset.model.access_qs(self.request.user, queryset=queryset)
        )

    def get_serializer_class(self):
        return serializers.OrganizationSerializer

    def get_response_serializer_class(self):
        return serializers.OrganizationSerializer

    @extend_schema(
        exclude=not settings.ALLOW_LOCAL_RESOURCE_MANAGEMENT,
        description="Delete an organization by id",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None, description="Delete successful."
            ),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                None, description="Default Organization cannot be deleted."
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                None, description="Delete is prohibited"
            ),
        },
    )
    def destroy(self, request, *args, **kwargs):
        self.validate_shared_resource()
        instance = self.get_object()

        if instance.name == settings.DEFAULT_ORGANIZATION_NAME:
            raise api_exc.Conflict(
                "The default organization cannot be deleted."
            )

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

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
        methods=["get"],
        queryset=models.Team.objects.order_by("id"),
        filterset_class=filters.OrganizationTeamFilter,
        rbac_action=Action.READ,
        url_path="(?P<id>[^/.]+)/teams",
    )
    def teams(self, request, id):
        org_exists = (
            models.Organization.access_qs(request.user).filter(id=id).exists()
        )
        if not org_exists:
            raise api_exc.NotFound(
                code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization with ID={id} does not exist.",
            )

        teams = models.Team.objects.filter(organization_id=id)
        filtered_teams = self.filter_queryset(teams)
        result = self.paginate_queryset(filtered_teams)
        serializer = serializers.TeamSerializer(result, many=True)
        return self.get_paginated_response(serializer.data)
