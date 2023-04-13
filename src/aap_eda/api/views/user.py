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
from django.contrib.auth.hashers import make_password
from django.shortcuts import get_list_or_404
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, permissions, status, views, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from aap_eda.api import serializers
from aap_eda.api.exceptions import Conflict
from aap_eda.core import models

from .mixins import PartialUpdateOnlyModelMixin, ResponseSerializerMixin


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
        description="List current user AWX tokens.",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.AwxTokenSerializer,
                description="Return a list of AWX tokens.",
            ),
        },
    ),
    retrieve=extend_schema(
        description="Get current user AWX token by ID.",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.AwxTokenSerializer,
                description="Return a AWX tokens.",
            ),
        },
    ),
    create=extend_schema(
        description="Create a AWX token for a current user.",
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.AwxTokenSerializer,
                description="Return the created AWX token.",
            ),
        },
    ),
    destroy=extend_schema(
        description="Delete AWX token of a current user by ID.",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="The AWX token has been deleted.",
            ),
        },
    ),
)
class CurrentUserAwxTokensViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    GenericViewSet,
):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = serializers.AwxTokenSerializer

    def get_queryset(self):
        return models.AwxToken.objects.filter(user=self.request.user).order_by(
            "id"
        )

    def perform_create(self, serializer):
        try:
            serializer.save(user=self.request.user)
        except django.db.utils.IntegrityError:
            name_exists = models.AwxToken.objects.filter(
                user=self.request.user, name=serializer.validated_data["name"]
            ).exists()
            if name_exists:
                raise Conflict("Token with this name already exists.")
            raise Conflict


@extend_schema_view(
    list=extend_schema(
        description="List all users",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.UserListSerializer,
                description="Return a list of users.",
            ),
        },
    ),
    retrieve=extend_schema(
        description="Retrieve a user by their id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.UserSerializer,
                description="Return a user.",
            ),
        },
    ),
    partial_update=extend_schema(
        description="Partial update of a user.",
        request=serializers.UserCreateUpdateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.UserSerializer,
                description="Update successful. Return an updated user.",
            )
        },
    ),
)
class UserViewSet(
    viewsets.ReadOnlyModelViewSet,
    PartialUpdateOnlyModelMixin,
    ResponseSerializerMixin,
):
    queryset = models.User.objects.order_by("id")

    def get_serializer_class(self):
        if self.action == "list":
            return serializers.UserListSerializer
        elif self.action in ["retrieve", "create", "partial_update"]:
            return serializers.UserSerializer
        elif self.action == "tokens":
            return serializers.AwxTokenListSerializer

    @extend_schema(
        description="Create a user",
        request=serializers.UserCreateUpdateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.UserSerializer,
                description="Return the created user.",
            ),
        },
    )
    def create(self, request):
        request.data["password"] = make_password(request.data["password"])
        serializer = serializers.UserCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        serializer = self.get_serializer(user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        description="list of AWK tokens for the user.",
        request=None,
        responses={
            status.HTTP_200_OK: serializers.AwxTokenListSerializer(many=True)
        },
    )
    @action(detail=True, methods=["get"])
    def tokens(self, request, pk):
        tokens = get_list_or_404(models.AwxToken, user=pk)
        serializer = self.get_serializer(tokens)
        return Response(serializer.data, status=status.HTTP_200_OK)
