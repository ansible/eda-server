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


class TaskRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    href = serializers.SerializerMethodField()

    @extend_schema_field(serializers.URLField)
    def get_href(self, data: dict):
        return reverse(
            "task-detail", args=[data["id"]], request=self.context["request"]
        )


class TaskSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=[x.value for x in JobStatus])
    created_at = serializers.DateTimeField(allow_null=True)
    enqueued_at = serializers.DateTimeField(allow_null=True)
    started_at = serializers.DateTimeField(allow_null=True)
    finished_at = serializers.DateTimeField(allow_null=True)

    def to_representation(self, instance):
        data = instance.to_dict()
        return {
            "id": instance.id,
            "status": data["status"],
            "created_at": data["created_at"] or None,
            "enqueued_at": data["enqueued_at"] or None,
            "started_at": data["started_at"] or None,
            "finished_at": data["ended_at"] or None,
        }
