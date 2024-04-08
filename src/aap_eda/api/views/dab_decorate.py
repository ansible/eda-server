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
