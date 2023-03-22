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
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.ExtraVarSerializer,
                description="Return the created extra_var.",
            ),
        },
    ),
)
class ExtraVarViewSet(
    mixins.CreateModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.ExtraVar.objects.order_by("id")
    serializer_class = serializers.ExtraVarSerializer
    http_method_names = ["get", "post"]


@extend_schema_view(
    retrieve=extend_schema(
        description="Get the playbook by its id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.PlaybookSerializer,
                description="Return the playbook by its id.",
            ),
        },
    ),
    list=extend_schema(
        description="List all playbooks",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.PlaybookSerializer,
                description="Return a list of playbooks.",
            ),
        },
    ),
)
class PlaybookViewSet(
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.Playbook.objects.all().order_by("id")
    serializer_class = serializers.PlaybookSerializer


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
    retrieve=extend_schema(
        description="Get project by id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ProjectSerializer,
                description="Return a project by id.",
            ),
        },
    ),
    update=extend_schema(
        description="Update a project",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ProjectSerializer,
                description="Update successful. Return an updated project.",
            )
        },
    ),
    partial_update=extend_schema(
        description="Partial update of a project",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ProjectSerializer,
                description="Update successful. Return an updated project.",
            )
        },
    ),
    destroy=extend_schema(
        description="Delete a project by id",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                serializers.ProjectSerializer, description="Delete successful."
            )
        },
    ),
)
class ProjectViewSet(viewsets.ModelViewSet):
    queryset = models.Project.objects.order_by("id")
    serializer_class = serializers.ProjectSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = filters.ProjectFilter

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
        project = serializer.save()

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
        responses={status.HTTP_202_ACCEPTED: serializers.TaskRefSerializer}
    )
    @action(methods=["post"], detail=True)
    def sync(self, request, pk):
        project_exists = models.Project.objects.filter(pk=pk).exists()
        if not project_exists:
            raise api_exc.NotFound

        job = tasks.sync_project.delay(project_id=int(pk))
        serializer = serializers.TaskRefSerializer(
            {"id": job.id}, context={"request": request}
        )
        return Response(status=status.HTTP_202_ACCEPTED, data=serializer.data)
