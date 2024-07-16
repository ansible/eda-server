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
from ansible_base.rbac.api.permissions import AnsibleBaseUserPermissions
from ansible_base.rbac.policies import visible_users
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, permissions, status, views, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from aap_eda.api import filters, serializers
from aap_eda.core import models

from .mixins import (
    CreateModelMixin,
    PartialUpdateOnlyModelMixin,
    ResponseSerializerMixin,
    SharedResourceViewMixin,
)


class CurrentUserView(views.APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        operation_id="get_current_user",
        description="Get current user.",
        request=None,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                description="Return current user.",
                response=serializers.UserDetailSerializer,
            ),
        },
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        user = request.user
        serializer = serializers.UserDetailSerializer(user)
        return Response(data=serializer.data)

    @extend_schema(
        exclude=not settings.ALLOW_LOCAL_RESOURCE_MANAGEMENT,
        operation_id="update_current_user",
        description="Update current user.",
        request=serializers.CurrentUserUpdateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                description="Return current user.",
                response=serializers.UserDetailSerializer,
            )
        },
    )
    def patch(self, request: Request, *args, **kwargs) -> Response:
        user = request.user
        serializer = serializers.CurrentUserUpdateSerializer(
            user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_serializer = serializers.UserDetailSerializer(user)
        return Response(response_serializer.data)


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
        parameters=[
            OpenApiParameter(
                "id",
                type=int,
                location=OpenApiParameter.PATH,
                description="A unique integer value identifying this token.",
            )
        ],
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.AwxTokenSerializer,
                description="Return a AWX tokens.",
            ),
        },
    ),
    create=extend_schema(
        description="Create a AWX token for a current user.",
        request=serializers.AwxTokenCreateSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.AwxTokenSerializer,
                description="Return the created AWX token.",
            ),
        },
    ),
    destroy=extend_schema(
        description="Delete AWX token of a current user by ID.",
        parameters=[
            OpenApiParameter(
                "id",
                type=int,
                location=OpenApiParameter.PATH,
                description="A unique integer value identifying this token.",
            )
        ],
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="The AWX token has been deleted.",
            ),
        },
    ),
)
class CurrentUserAwxTokenViewSet(
    CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    GenericViewSet,
):
    permission_classes = (permissions.IsAuthenticated,)

    def get_serializer_class(self):
        if self.action == "create":
            return serializers.AwxTokenCreateSerializer

        return serializers.AwxTokenSerializer

    def get_response_serializer_class(self):
        return serializers.AwxTokenSerializer

    def get_queryset(self):
        return models.AwxToken.objects.filter(user=self.request.user).order_by(
            "id"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@extend_schema_view(
    create=extend_schema(
        exclude=not settings.ALLOW_LOCAL_RESOURCE_MANAGEMENT,
        description="Create a user",
        request=serializers.UserCreateUpdateSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.UserDetailSerializer,
                description="Return the created user.",
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                None, description="Create is prohibited"
            ),
        },
    ),
    list=extend_schema(
        description="List users",
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
                serializers.UserDetailSerializer,
                description="Return a user.",
            ),
        },
    ),
    partial_update=extend_schema(
        exclude=not settings.ALLOW_LOCAL_RESOURCE_MANAGEMENT,
        description="Partial update of a user.",
        request=serializers.UserCreateUpdateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.UserDetailSerializer,
                description="Update successful. Return an updated user.",
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                None, description="Update is prohibited"
            ),
        },
    ),
    destroy=extend_schema(
        exclude=not settings.ALLOW_LOCAL_RESOURCE_MANAGEMENT,
        description="Delete a user by id",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="The user has been deleted successful.",
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                None,
                description="Delete is prohibited",
            ),
        },
    ),
)
class UserViewSet(
    viewsets.ReadOnlyModelViewSet,
    CreateModelMixin,
    PartialUpdateOnlyModelMixin,
    ResponseSerializerMixin,
    mixins.DestroyModelMixin,
    SharedResourceViewMixin,
):
    queryset = models.User.objects.filter(is_service_account=False).order_by(
        "id"
    )
    filter_backends = (DjangoFilterBackend,)
    permission_classes = [AnsibleBaseUserPermissions]
    filterset_class = filters.UserFilter

    def filter_queryset(self, qs):
        qs = visible_users(self.request.user, queryset=qs)
        if not self.kwargs or "pk" not in self.kwargs:
            # TODO: hardcode for now, will need to use settings.SYSTEM_USERNAME
            qs = qs.exclude(username="_system")
        return super().filter_queryset(qs)

    def get_serializer_class(self):
        if self.action == "list":
            return serializers.UserListSerializer
        elif self.action == "destroy":
            return serializers.UserSerializer
        elif self.action in ["create", "partial_update"]:
            return serializers.UserCreateUpdateSerializer

        return serializers.UserDetailSerializer

    def get_response_serializer_class(self):
        return serializers.UserDetailSerializer

    def destroy(self, request, *args, **kwargs):
        self.validate_shared_resource()
        instance = self.get_object()

        if instance == request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
