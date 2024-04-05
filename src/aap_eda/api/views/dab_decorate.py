from ansible_base.rbac.api.serializers import RoleDefinitionSerializer
from ansible_base.rbac.api.views import RoleDefinitionViewSet
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status

extend_schema(
    description="Create a RoleDefinition.",
    responses={
        status.HTTP_201_CREATED: OpenApiResponse(
            RoleDefinitionSerializer,
            description="Return a created RoleDefinition.",
        ),
    },
)(RoleDefinitionViewSet.create)
