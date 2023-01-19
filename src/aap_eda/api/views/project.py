from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, viewsets

from aap_eda.api import serializers
from aap_eda.core import models


@extend_schema_view(
    retrieve=extend_schema(
        description="Get the extra_var by its id",
        responses={
            200: OpenApiResponse(
                serializers.ExtraVarSerializer,
                description=("Return the extra_var by its id."),
            ),
        },
    ),
    list=extend_schema(
        description="List all extra_vars",
        responses={
            200: OpenApiResponse(
                serializers.ExtraVarSerializer,
                description=("Return a list of extra_vars."),
            ),
        },
    ),
    create=extend_schema(
        description="Create an extra_var",
        responses={
            201: OpenApiResponse(
                serializers.ExtraVarSerializer,
                description=("Return the created extra_var."),
            ),
        },
    ),
)
class ExtraVarViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.ExtraVar.objects.all()
    serializer_class = serializers.ExtraVarSerializer
    http_method_names = ["get", "post"]


@extend_schema_view(
    retrieve=extend_schema(
        description="Get the playbook by its id",
        responses={
            200: OpenApiResponse(
                serializers.PlaybookSerializer,
                description=("Return the playbook by its id."),
            ),
        },
    ),
    list=extend_schema(
        description="List all playbooks",
        responses={
            200: OpenApiResponse(
                serializers.PlaybookSerializer,
                description=("Return a list of playbooks."),
            ),
        },
    ),
    create=extend_schema(
        description="Create a playbook",
        responses={
            201: OpenApiResponse(
                serializers.PlaybookSerializer,
                description=("Return the created playbook."),
            ),
        },
    ),
    destroy=extend_schema(
        description="Delete an existing playbook",
        responses={
            204: OpenApiResponse(
                None,
                description=("The playbook is deleted."),
            ),
        },
    ),
)
class PlaybookViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.Playbook.objects.all()
    serializer_class = serializers.PlaybookSerializer
    http_method_names = ["get", "post", "delete"]
