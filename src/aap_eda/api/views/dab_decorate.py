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
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status

from ansible_base.rbac.api.router import router as rbac_router

from aap_eda.api.views.dab_base import convert_to_create_serializer

for viewset_cls in [
    views.RoleDefinitionViewSet,
    views.RoleUserAssignmentViewSet,
    views.RoleTeamAssignmentViewSet,
]:
    cls_name = viewset_cls.__name__.replace("ViewSet", "")
    extend_schema_view(
        create=extend_schema(
            description=f"Create a {cls_name}.",
            request=convert_to_create_serializer(viewset_cls.serializer_class),
            responses={
                status.HTTP_201_CREATED: OpenApiResponse(
                    viewset_cls.serializer_class,
                    description=f"Return a created {cls_name}.",
                ),
            },
        ),
    )(viewset_cls)


for url, viewset, view_name in rbac_router.registry:
    if view_name in (
        "roledefinition-user_assignments",
        "roledefinition-team_assignments",
    ):
        extend_schema_view(
            list=extend_schema(
                request=None,
                parameters=[
                    OpenApiParameter(
                        name="id",
                        type=int,
                        location=OpenApiParameter.PATH,
                        description="A unique integer value identifying this assignment.",  # noqa: E501
                    )
                ],
            )
        )(viewset)
