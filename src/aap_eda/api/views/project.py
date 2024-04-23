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
from ansible_base.rbac.api.related import check_related_permissions
from ansible_base.rbac.models import RoleDefinition
from django.db import transaction
from django.forms import model_to_dict
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from aap_eda import tasks
from aap_eda.api import exceptions as api_exc, filters, serializers
from aap_eda.api.serializers.project import (
    ENCRYPTED_STRING,
    get_proxy_for_display,
)
from aap_eda.core import models
from aap_eda.core.enums import Action

from .mixins import CreateModelMixin, ResponseSerializerMixin


@extend_schema_view(
    retrieve=extend_schema(
        description="Get the extra_var by its id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ExtraVarSerializer,
                description="Return the extra_var by its id.",
            ),
        },
    ),
    list=extend_schema(
        description="List all extra_vars",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ExtraVarSerializer,
                description="Return a list of extra_vars.",
            ),
        },
    ),
    create=extend_schema(
        description="Create an extra_var",
        request=serializers.ExtraVarCreateSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.ExtraVarSerializer,
                description="Return the created extra_var.",
            ),
        },
    ),
)
class ExtraVarViewSet(
    CreateModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.ExtraVar.objects.order_by("id")
    serializer_class = serializers.ExtraVarSerializer
    http_method_names = ["get", "post"]

    def filter_queryset(self, queryset):
        return super().filter_queryset(
            queryset.model.access_qs(self.request.user, queryset=queryset)
        )

    def get_serializer_class(self):
        if self.action == "create":
            return serializers.ExtraVarCreateSerializer
        return super().get_serializer_class()

    def get_response_serializer_class(self):
        return serializers.ExtraVarSerializer


@extend_schema_view(
    list=extend_schema(
        description="List all projects",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ProjectSerializer,
                description="Return a list of projects.",
            ),
        },
    ),
    destroy=extend_schema(
        description="Delete a project by id",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="Delete successful.",
            ),
        },
    ),
)
class ProjectViewSet(
    ResponseSerializerMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.Project.objects.order_by("id")
    serializer_class = serializers.ProjectSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = filters.ProjectFilter

    rbac_action = None

    def filter_queryset(self, queryset):
        return super().filter_queryset(
            queryset.model.access_qs(self.request.user, queryset=queryset)
        )

    @extend_schema(
        description="Import a project.",
        request=serializers.ProjectCreateRequestSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.ProjectSerializer,
                description="Return a created project.",
            ),
        },
    )
    def create(self, request):
        serializer = serializers.ProjectCreateRequestSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            project = serializer.save()
            check_related_permissions(
                request.user,
                serializer.Meta.model,
                {},
                model_to_dict(serializer.instance),
            )
            RoleDefinition.objects.give_creator_permissions(
                request.user, serializer.instance
            )

        job = tasks.import_project.delay(project_id=project.id)

        # Atomically update `import_task_id` field only.
        models.Project.objects.filter(pk=project.id).update(
            import_task_id=job.id
        )
        project.import_task_id = job.id
        serializer = self.get_serializer(project)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    @extend_schema(
        description="Get a project by id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ProjectReadSerializer,
                description="Return a project by id.",
            ),
        },
    )
    def retrieve(self, request, pk):
        project = super().retrieve(request, pk)
        project.data["eda_credential"] = (
            models.EdaCredential.objects.get(
                pk=project.data["eda_credential_id"]
            )
            if project.data["eda_credential_id"]
            else None
        )
        project.data["signature_validation_credential"] = (
            models.EdaCredential.objects.get(
                pk=project.data["signature_validation_credential_id"]
            )
            if project.data["signature_validation_credential_id"]
            else None
        )
        project.data["organization"] = (
            models.Organization.objects.get(pk=project.data["organization_id"])
            if project.data["organization_id"]
            else None
        )

        return Response(serializers.ProjectReadSerializer(project.data).data)

    @extend_schema(
        description="Partial update of a project",
        request=serializers.ProjectUpdateRequestSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ProjectSerializer,
                description="Update successful. Return an updated project.",
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                None,
                description="Update failed with bad request.",
            ),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                None,
                description="Update failed with integrity checking.",
            ),
        },
    )
    def partial_update(self, request, pk):
        project = self.get_object()
        if "proxy" in request.data:
            new_proxy = request.data["proxy"]
            if ENCRYPTED_STRING in new_proxy:
                unchanged = (
                    project.proxy
                    and get_proxy_for_display(project.proxy.get_secret_value())
                    == new_proxy
                )
                if unchanged:
                    request.data.pop("proxy")
                else:
                    error = (
                        "The password in the proxy field should be unencrypted"
                    )
                    return Response(
                        {"errors": error}, status=status.HTTP_400_BAD_REQUEST
                    )
        serializer = serializers.ProjectUpdateRequestSerializer(
            instance=project, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)

        update_fields = []
        for key, value in serializer.validated_data.items():
            setattr(project, key, value)
            update_fields.append(key)

        old_data = model_to_dict(project)
        with transaction.atomic():
            project.save(update_fields=update_fields)
            check_related_permissions(
                request.user,
                serializer.Meta.model,
                old_data,
                model_to_dict(project),
            )

        return Response(serializers.ProjectSerializer(project).data)

    @extend_schema(
        responses={status.HTTP_202_ACCEPTED: serializers.ProjectSerializer},
        request=None,
        description="Sync a project",
    )
    @action(
        methods=["post"],
        detail=True,
        rbac_action=Action.UPDATE,
    )
    @transaction.atomic
    def sync(self, request, pk):
        try:
            project = self.get_queryset().select_for_update().get(pk=pk)
        except models.Project.DoesNotExist:
            raise api_exc.NotFound

        if project.import_state in [
            models.Project.ImportState.PENDING,
            models.Project.ImportState.RUNNING,
        ]:
            raise api_exc.Conflict(
                detail="Project import or sync is already running."
            )

        job = tasks.sync_project.delay(project_id=project.id)

        project.import_state = models.Project.ImportState.PENDING
        project.import_task_id = job.id
        project.import_error = None
        project.save()

        serializer = serializers.ProjectSerializer(project)
        return Response(status=status.HTTP_202_ACCEPTED, data=serializer.data)
