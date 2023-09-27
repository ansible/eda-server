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
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import authentication, permissions, status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from aap_eda.api import exceptions, filters, serializers
from aap_eda.api.serializers import LoginSerializer
from aap_eda.core import models
from aap_eda.services.auth import display_permissions


class SessionLoginView(APIView):
    permission_classes = ()

    @extend_schema(
        operation_id="auth_session_preflight",
        description="Use this method to set a CSRF cookie.",
        request=LoginSerializer,
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(description="OK"),
        },
    )
    @method_decorator(ensure_csrf_cookie)
    @method_decorator(never_cache)
    def get(self, request: Request, *args, **kwargs):
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        operation_id="auth_session_login",
        description="Session cookie login",
        request=LoginSerializer,
        responses={
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                description="Invalid credentials or user is disabled."
            ),
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                description="Login successful."
            ),
        },
    )
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def post(self, request: Request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = authenticate(
            request, username=data["username"], password=data["password"]
        )

        if user is None:
            raise exceptions.PermissionDenied(
                "Invalid credentials or user is disabled."
            )

        login(request, user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionLogoutView(APIView):
    authentication_classes = (authentication.SessionAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        operation_id="auth_session_logout",
        description="Session logout.",
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                description="Logout successful."
            ),
        },
    )
    @method_decorator(never_cache)
    def post(self, request: Request, *args, **kwargs):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    list=extend_schema(
        description="List all roles",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.RoleListSerializer,
                description="Return a list of roles.",
            ),
        },
    )
)
class RoleViewSet(
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.Role.objects.order_by("id")
    filter_backends = (DjangoFilterBackend,)
    filterset_class = filters.RoleFilter

    def get_serializer_class(self):
        if self.action == "list":
            return serializers.RoleListSerializer
        elif self.action == "retrieve":
            return serializers.RoleDetailSerializer

    @extend_schema(
        description="Retrieve a role by id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.RoleDetailSerializer,
                description="Return a role.",
            ),
        },
    )
    def retrieve(self, _request, pk=None):
        # TODO: Optimization by querying to retrieve desired permission format
        role = get_object_or_404(self.queryset, pk=pk)

        detail_serialzer = self.get_serializer_class()
        role = detail_serialzer(role).data
        result = display_permissions(role)

        return Response(result)
