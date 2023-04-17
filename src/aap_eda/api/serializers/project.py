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

from rest_framework import serializers

from aap_eda.core import models


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Project
        read_only_fields = [
            "id",
            "url",
            "git_hash",
            "import_state",
            "import_error",
            "import_task_id",
            "created_at",
            "modified_at",
        ]
        fields = ["name", "description", *read_only_fields]


class ProjectCreateRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Project
        fields = ["url", "name", "description"]


class ProjectRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Project
        fields = ["id", "git_hash", "url", "name", "description"]
        read_only_fields = ["id"]


class ExtraVarSerializer(serializers.ModelSerializer):
    extra_var = serializers.CharField(
        required=True,
        help_text="Content of the extra_var",
    )

    class Meta:
        model = models.ExtraVar
        fields = ["id", "extra_var"]
        read_only_fields = ["id"]


class ExtraVarRefSerializer(serializers.ModelSerializer):
    """Serializer for Extra Var reference."""

    class Meta:
        model = models.ExtraVar
        fields = ["id"]
        read_only_fields = ["id"]


class PlaybookSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True,
        help_text="Name of the playbook",
    )

    playbook = serializers.CharField(
        required=True,
        help_text="Content of the playbook",
    )

    class Meta:
        model = models.Playbook
        fields = "__all__"
        read_only_fields = ["id"]
