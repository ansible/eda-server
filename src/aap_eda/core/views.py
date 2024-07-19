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

from django.db import connection
from django.db.utils import OperationalError
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import StatusResponseSerializer


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            connection.ensure_connection()
            return Response({"status": "OK"}, status=status.HTTP_200_OK)
        except OperationalError:
            return Response(
                {"status": "error", "message": "Database connection failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StatusView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        description="Get the current status of EDA.",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                StatusResponseSerializer,
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                StatusResponseSerializer,
            ),
        },
    )
    def get(self, request):
        try:
            connection.ensure_connection()
            return Response({"status": "OK"}, status=status.HTTP_200_OK)
        except OperationalError:
            return Response(
                {"status": "error", "message": "Database connection failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
