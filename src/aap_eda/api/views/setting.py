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

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from aap_eda.api.serializers.setting import SettingSerializer
from aap_eda.conf import settings_registry


class SettingView(APIView):
    permission_classes = [IsAdminUser]

    def get_serializer(self, *args, **kwargs):
        return SettingSerializer(*args, **kwargs)

    @extend_schema(
        description="Get application system settings",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                SettingSerializer,
                description=("Return application system settings"),
            )
        },
    )
    def get(self, request):
        data = settings_registry.db_get_settings_for_display()
        return Response(SettingSerializer(data).data)

    @extend_schema(
        description="Partially update application system settings",
        request=SettingSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                SettingSerializer,
                description="Return updated system settings.",
            ),
        },
    )
    def patch(self, request: Request):
        serializer = SettingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        settings_registry.db_update_settings(serializer.validated_data)

        return self.get(None)
