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

from aap_eda.api.serializers.inventory import InventoryRefSerializer
from aap_eda.api.serializers.project import (
    ExtraVarRefSerializer,
    ProjectRefSerializer,
)
from aap_eda.api.serializers.rulebook import RulebookRefSerializer
from aap_eda.core import models


class ActivationSerializer(serializers.ModelSerializer):
    """Serializer for the Activation model."""

    class Meta:
        model = models.Activation
        fields = "__all__"
        read_only_fields = ["id"]


class ActivationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating the Activation."""

    project_id = serializers.IntegerField(required=False)
    rulebook_id = serializers.IntegerField()
    inventory_id = serializers.IntegerField()
    extra_var_id = serializers.IntegerField(required=False)

    class Meta:
        model = models.Activation
        fields = [
            "name",
            "description",
            "is_enabled",
            "working_directory",
            "execution_environment",
            "project_id",
            "rulebook_id",
            "inventory_id",
            "extra_var_id",
            "restart_policy",
        ]


class ActivationUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating the Activation."""

    class Meta:
        model = models.Activation
        fields = [
            "name",
            "description",
            "is_enabled",
        ]


class ActivationInstanceSerializer(serializers.ModelSerializer):
    """Serializer for the Activation Instance model."""

    class Meta:
        model = models.ActivationInstance
        fields = "__all__"
        read_only_fields = ["id", "started_at", "ended_at"]


class ActivationInstanceLogSerializer(serializers.ModelSerializer):
    """Serializer for the Activation Instance Log model."""

    class Meta:
        model = models.ActivationInstanceLog
        fields = "__all__"
        read_only_fields = ["id"]


class ActivationReadSerializer(serializers.ModelSerializer):
    """Serializer for reading the Activation with related objects info."""

    project = ProjectRefSerializer(required=False)
    rulebook = RulebookRefSerializer()
    inventory = InventoryRefSerializer()
    extra_var = ExtraVarRefSerializer(required=False)
    instances = ActivationInstanceSerializer(many=True)

    class Meta:
        model = models.Activation
        fields = [
            "id",
            "name",
            "description",
            "is_enabled",
            "working_directory",
            "execution_environment",
            "project",
            "rulebook",
            "inventory",
            "extra_var",
            "instances",
            "restart_policy",
            "restart_count",
            "created_at",
            "modified_at",
        ]
        read_only_fields = ["id", "created_at", "modified_at"]

    def to_representation(self, activation):
        project = (
            ProjectRefSerializer(activation["project"]).data
            if activation["project"]
            else None
        )
        extra_var = (
            ExtraVarRefSerializer(activation["extra_var"]).data
            if activation["extra_var"]
            else None
        )
        return {
            "id": activation["id"],
            "name": activation["name"],
            "description": activation["description"],
            "is_enabled": activation["is_enabled"],
            "working_directory": activation["working_directory"],
            "execution_environment": activation["execution_environment"],
            "project": project,
            "rulebook": RulebookRefSerializer(activation["rulebook"]).data,
            "inventory": InventoryRefSerializer(activation["inventory"]).data,
            "extra_var": extra_var,
            "instances": ActivationInstanceSerializer(
                activation["instances"], many=True
            ).data,
            "restart_policy": activation["restart_policy"],
            "restart_count": activation["restart_count"],
            "created_at": activation["created_at"],
            "modified_at": activation["modified_at"],
        }
