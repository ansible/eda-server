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
from itertools import chain
from typing import Iterator, Optional

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from aap_eda.api import serializers
from aap_eda.core.tasking import Job, get_queue


class TaskViewSet(ViewSet):
    @extend_schema(
        responses={status.HTTP_200_OK: serializers.TaskSerializer},
    )
    def list(self, _request):
        jobs = list_jobs()
        serializer = serializers.TaskSerializer(jobs, many=True)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter("id", OpenApiTypes.UUID, OpenApiParameter.PATH)
        ],
        responses={
            status.HTTP_200_OK: serializers.TaskSerializer,
        },
    )
    def retrieve(self, _request, pk):
        job = get_job(pk)
        if job is None:
            raise exceptions.NotFound
        serializer = serializers.TaskSerializer(job)
        return Response(serializer.data)


def list_jobs() -> Iterator[Job]:
    queue = get_queue()
    all_job_ids = chain(
        queue.get_job_ids(),
        queue.started_job_registry.get_job_ids(),
        queue.failed_job_registry.get_job_ids(),
        queue.scheduled_job_registry.get_job_ids(),
        queue.finished_job_registry.get_job_ids(),
        queue.canceled_job_registry.get_job_ids(),
        queue.deferred_job_registry.get_job_ids(),
    )
    return map(queue.fetch_job, all_job_ids)


def get_job(job_id: str) -> Optional[Job]:
    queue = get_queue()
    return queue.fetch_job(job_id)
