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
    extend_schema_view(
        create=extend_schema(
            description="Create a RoleDefinition.",
            responses={
                status.HTTP_201_CREATED: OpenApiResponse(
                    viewset_cls.serializer_class,
                    description="Return a created RoleDefinition.",
                ),
            },
        ),
    )(viewset_cls)
