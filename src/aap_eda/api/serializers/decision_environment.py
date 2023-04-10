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


class DecisionEnvironmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DecisionEnvironment
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
        ]
        fields = [
            "name",
            "description",
            "image_url",
            "credential",
            *read_only_fields,
        ]


class DecisionEnvironmentRefSerializer(serializers.ModelSerializer):
    """Serializer for DecisionEnvironment reference."""

    class Meta:
        model = models.DecisionEnvironment
        fields = ["id", "name", "description", "image_url"]
        read_only_fields = ["id"]
