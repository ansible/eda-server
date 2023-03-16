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
import django.db.utils
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, permissions, status, views
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from aap_eda.api import serializers
from aap_eda.api.exceptions import Conflict
from aap_eda.core import models


class CurrentUserView(views.APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        operation_id="retrieve_current_user",
        description="Get current user.",
        request=None,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                description="Return current user.",
                response=serializers.UserSerializer,
            ),
        },
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        user = request.user
        serializer = serializers.UserSerializer(user)
        return Response(data=serializer.data)


@extend_schema_view(
    list=extend_schema(
        description="List current user controller tokens.",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ControllerTokenSerializer,
                description="Return a list of controller tokens.",
            ),
        },
    ),
    retrieve=extend_schema(
        description="Get current user controller token by ID.",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ControllerTokenSerializer,
                description="Return a controller tokens.",
            ),
        },
    ),
    create=extend_schema(
        description="Create a controller token for a current user.",
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.ControllerTokenSerializer,
                description="Return the created controller token.",
            ),
        },
    ),
    destroy=extend_schema(
        description="Delete controller token of a current user by ID.",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="The controller token has been deleted.",
            ),
        },
    ),
)
class CurrentUserControllerTokensViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    GenericViewSet,
):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = serializers.ControllerTokenSerializer

    def get_queryset(self):
        return models.ControllerToken.objects.filter(
            user=self.request.user
        ).order_by("id")

    def perform_create(self, serializer):
        try:
            serializer.save(user=self.request.user)
        except django.db.utils.IntegrityError:
            name_exists = models.ControllerToken.objects.filter(
                user=self.request.user, name=serializer.validated_data["name"]
            ).exists()
            if name_exists:
                raise Conflict("Token with this name already exists.")
            raise Conflict
