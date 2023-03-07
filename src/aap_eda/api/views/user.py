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
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from aap_eda.api import serializers


class CurrentUserView(APIView):
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
