from ansible_base.rbac.api.views import RoleDefinitionViewSet
from ansible_base.rbac.api.serializers import RoleDefinitionSerializer

from rest_framework import status

from drf_spectacular.utils import OpenApiResponse, extend_schema


extend_schema(
    description="Create a RoleDefinition.",
    responses={
        status.HTTP_201_CREATED: OpenApiResponse(
            RoleDefinitionSerializer,
            description="Return a created RoleDefinition.",
        ),
    },
)(RoleDefinitionViewSet.create)
