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

from ansible_base.rbac.api import views
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status

for viewset_cls in [
    views.RoleDefinitionViewSet,
    views.RoleUserAssignmentViewSet,
    views.RoleTeamAssignmentViewSet,
]:
    cls_name = viewset_cls.__name__.replace("ViewSet", "")
    extend_schema_view(
        create=extend_schema(
            description=f"Create a {cls_name}.",
            responses={
                status.HTTP_201_CREATED: OpenApiResponse(
                    viewset_cls.serializer_class,
                    description=f"Return a created {cls_name}.",
                ),
            },
        ),
    )(viewset_cls)
