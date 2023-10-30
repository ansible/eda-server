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
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.reverse import reverse
from rq.job import JobStatus

from aap_eda.core.tasking import Job


class TaskRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    href = serializers.SerializerMethodField()

    @extend_schema_field(serializers.URLField)
    def get_href(self, data: dict):
        return reverse("task-detail", args=[data["id"]], request=self.context["request"])


class TaskSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(allow_null=True)
    enqueued_at = serializers.DateTimeField(allow_null=True)
    started_at = serializers.DateTimeField(allow_null=True)
    finished_at = serializers.DateTimeField(allow_null=True, source="ended_at")
    result = serializers.JSONField()

    @extend_schema_field(serializers.ChoiceField(choices=[x.value for x in JobStatus]))
    def get_status(self, instance: Job) -> str:
        return instance.get_status()
