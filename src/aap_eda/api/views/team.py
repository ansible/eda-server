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

from django_filters import rest_framework as defaultfilters
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets

from aap_eda.api.filters import TeamFilter
from aap_eda.api.serializers import (
    TeamCreateSerializer,
    TeamSerializer,
    TeamUpdateSerializer,
)
from aap_eda.core import models
from aap_eda.core.enums import ResourceType

from .mixins import PartialUpdateOnlyModelMixin


@extend_schema_view(
    list=extend_schema(
        description="List all teams.",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                TeamSerializer,
                description="Return a list of teams.",
            ),
        },
    ),
    create=extend_schema(
        description="Create a new team",
        request=TeamCreateSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                TeamSerializer,
                description="Return the new team.",
            ),
        },
    ),
    partial_update=extend_schema(
        description="Partially update a team",
        request=TeamUpdateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                TeamSerializer,
                description="Update successful. Return an updated team.",
            )
        },
    ),
)
class TeamViewSet(
    PartialUpdateOnlyModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.Team.objects.order_by("id")
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = TeamFilter
    rbac_resource_type = ResourceType.TEAM

    def get_serializer_class(self):
        return TeamSerializer

    def get_response_serializer_class(self):
        return TeamSerializer
