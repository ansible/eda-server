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
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import authentication, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from aap_eda.api import exceptions
from aap_eda.api.serializers import (
    JWTTokenSerializer,
    LoginSerializer,
    RefreshTokenSerializer,
)
from aap_eda.services.auth import jwt_access_token


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


class TokenRefreshView(APIView):
    permission_classes = ()
    authentication_classes = ()

    @extend_schema(
        operation_id="token_refresh",
        description="Refresh websocket access token",
        request=RefreshTokenSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(JWTTokenSerializer),
        },
    )
    @method_decorator(never_cache)
    def post(self, request: Request, *args, **kwargs):
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        access_token = {"access": jwt_access_token(serializer.user.id)}
        return Response(
            access_token,
            status=status.HTTP_200_OK,
        )
