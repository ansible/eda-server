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
import logging

# redis import removed - no longer required with dispatcherd migration
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
from aap_eda.core import models
from aap_eda.core.enums import Action
from aap_eda.core.utils import logging_utils

from .mixins import ResponseSerializerMixin

logger = logging.getLogger(__name__)

resource_name = "Project"


class DestroyProjectMixin(mixins.DestroyModelMixin):
    def destroy(self, request, *args, **kwargs):
        project = self.get_object()

        response = super().destroy(request, *args, **kwargs)

        logger.info(
            logging_utils.generate_simple_audit_log(
                "Delete",
                resource_name,
                project.name,
                project.id,
                project.organization,
            )
        )

        return response


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
    DestroyProjectMixin,
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
            )
        },
    )
    def create(self, request):
        serializer = serializers.ProjectCreateRequestSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        # With dispatcherd migration, Redis is no longer required
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

            job_id = tasks.import_project(project.id)

        models.Project.objects.filter(pk=project.id).update(
            import_task_id=job_id
        )
        project.import_task_id = job_id
        serializer = self.get_serializer(project)
        headers = self.get_success_headers(serializer.data)
        logger.info(
            logging_utils.generate_simple_audit_log(
                "Create",
                resource_name,
                project.name,
                project.id,
                project.organization,
            )
        )

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
        project = self.get_object()

        logger.info(
            logging_utils.generate_simple_audit_log(
                "Read",
                resource_name,
                project.name,
                project.id,
                project.organization.name,
            )
        )

        return Response(serializers.ProjectReadSerializer(project).data)

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
        serializer = serializers.ProjectUpdateRequestSerializer(
            instance=project, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)

        update_fields = []
        old_data = model_to_dict(project)

        for key, value in serializer.validated_data.items():
            setattr(project, key, value)
            update_fields.append(key)

        with transaction.atomic():
            project.save(update_fields=update_fields)
            check_related_permissions(
                request.user,
                serializer.Meta.model,
                old_data,
                model_to_dict(project),
            )

        logger.info(
            logging_utils.generate_simple_audit_log(
                "Update",
                resource_name,
                project.name,
                project.id,
                project.organization,
            )
        )

        if {"scm_branch", "scm_refspec", "url"}.intersection(
            update_fields
        ) and (
            project.import_state
            not in [
                models.Project.ImportState.PENDING,
                models.Project.ImportState.RUNNING,
            ]
        ):
            # With dispatcherd migration, Redis is no longer required

            job_id = tasks.sync_project(project.id)

            project.import_state = models.Project.ImportState.PENDING
            if job_id:
                project.import_task_id = job_id

            logger.info(
                f"Triggered import/sync task {job_id}"
                f" for project {project.id}"
            )

            project.save()

        return Response(serializers.ProjectSerializer(project).data)

    @extend_schema(
        responses={status.HTTP_202_ACCEPTED: serializers.ProjectSerializer},
        request=None,
        description="Sync a project",
    )
    @action(
        methods=["post"],
        detail=True,
        rbac_action=Action.SYNC,
    )
    @transaction.atomic
    def sync(self, request, pk):
        # get only projects user has access to
        try:
            project = (
                models.Project.access_qs(request.user)
                .select_for_update()
                .get(pk=pk)
            )
        except models.Project.DoesNotExist:
            raise api_exc.NotFound(f"Project with ID={pk} does not exist.")
        # user might have only view permission, so we still have to check if
        # user has sync permission for this project
        self.check_object_permissions(request, project)

        if project.import_state in [
            models.Project.ImportState.PENDING,
            models.Project.ImportState.RUNNING,
        ]:
            raise api_exc.Conflict(
                detail="Project import or sync is already running."
            )

        # With dispatcherd migration, Redis is no longer required
        job_id = tasks.sync_project(project.id)

        project.import_state = models.Project.ImportState.PENDING

        # job_id can be none if there is already a task running.
        # this is unlikely since we check the state above
        # but safety first
        if job_id:
            project.import_task_id = job_id

        project.save()

        logger.info(
            logging_utils.generate_simple_audit_log(
                "Sync",
                resource_name,
                project.name,
                project.id,
                project.organization,
            )
        )

        serializer = serializers.ProjectSerializer(project)
        return Response(status=status.HTTP_202_ACCEPTED, data=serializer.data)
