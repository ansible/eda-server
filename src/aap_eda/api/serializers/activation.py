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
import urllib.parse

from django.conf import settings
from django.db import IntegrityError
from rest_framework import serializers

from aap_eda.api.exceptions import (
    InvalidWebsocketHost,
    InvalidWebsocketScheme,
    NoControllerToken,
    TooManyControllerTokens,
)
from aap_eda.api.serializers.decision_environment import (
    DecisionEnvironmentRefSerializer,
)
from aap_eda.api.serializers.project import (
    ExtraVarRefSerializer,
    ProjectRefSerializer,
)
from aap_eda.api.serializers.rulebook import RulebookRefSerializer
from aap_eda.core import models
from aap_eda.services.ruleset.activate_rulesets import ACTIVATION_PATH


class ActivationSerializer(serializers.ModelSerializer):
    """Serializer for the Activation model."""

    class Meta:
        model = models.Activation
        fields = [
            "id",
            "name",
            "description",
            "is_enabled",
            "status",
            "git_hash",
            "decision_environment_id",
            "project_id",
            "rulebook_id",
            "extra_var_id",
            "restart_policy",
            "restart_count",
            "rulebook_name",
            "ruleset_stats",
            "current_job_id",
            "created_at",
            "modified_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
            "rulebook_name",
        ]


class ActivationListSerializer(serializers.ModelSerializer):
    """Serializer for listing the Activation model objects."""

    rules_count = serializers.IntegerField()
    rules_fired_count = serializers.IntegerField()

    class Meta:
        model = models.Activation
        fields = [
            "id",
            "name",
            "description",
            "is_enabled",
            "status",
            "decision_environment_id",
            "project_id",
            "rulebook_id",
            "extra_var_id",
            "restart_policy",
            "restart_count",
            "rulebook_name",
            "current_job_id",
            "rules_count",
            "rules_fired_count",
            "created_at",
            "modified_at",
        ]
        read_only_fields = ["id", "created_at", "modified_at"]


class ActivationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating the Activation."""

    rulebook_id = serializers.IntegerField()
    extra_var_id = serializers.IntegerField(required=False, allow_null=True)
    decision_environment_id = serializers.IntegerField()

    class Meta:
        model = models.Activation
        fields = [
            "name",
            "description",
            "is_enabled",
            "decision_environment_id",
            "rulebook_id",
            "extra_var_id",
            "restart_policy",
        ]

    def create(self, validated_data, user):
        self._validate_pre_reqs(user)
        try:
            rulebook = models.Rulebook.objects.get(
                pk=validated_data["rulebook_id"]
            )
        except models.Rulebook.DoesNotExist:
            raise IntegrityError
        validated_data["user_id"] = user.id
        validated_data["rulebook_name"] = rulebook.name
        validated_data["rulebook_rulesets"] = rulebook.rulesets
        validated_data["git_hash"] = rulebook.project.git_hash
        validated_data["project_id"] = rulebook.project.id
        return super().create(validated_data)

    def _validate_pre_reqs(self, user):
        tokens = models.AwxToken.objects.filter(user_id=user.id).count()
        if tokens == 0:
            raise NoControllerToken()
        elif tokens > 1:
            raise TooManyControllerTokens()

        ws_url = f"{settings.WEBSOCKET_BASE_URL}{ACTIVATION_PATH}"
        parsed_url = urllib.parse.urlparse(ws_url)

        if parsed_url.scheme not in ["ws", "wss"]:
            raise InvalidWebsocketScheme()
        if not parsed_url.hostname:
            raise InvalidWebsocketHost()


class ActivationInstanceSerializer(serializers.ModelSerializer):
    """Serializer for the Activation Instance model."""

    class Meta:
        model = models.ActivationInstance
        fields = [
            "id",
            "name",
            "status",
            "git_hash",
            "activation_id",
            "started_at",
            "ended_at",
        ]
        read_only_fields = ["id", "started_at", "ended_at"]


class ActivationInstanceLogSerializer(serializers.ModelSerializer):
    """Serializer for the Activation Instance Log model."""

    class Meta:
        model = models.ActivationInstanceLog
        fields = "__all__"
        read_only_fields = ["id"]


class ActivationReadSerializer(serializers.ModelSerializer):
    """Serializer for reading the Activation with related objects info."""

    decision_environment = DecisionEnvironmentRefSerializer(
        required=False, allow_null=True
    )
    project = ProjectRefSerializer(required=False, allow_null=True)
    rulebook = RulebookRefSerializer(required=False, allow_null=True)
    extra_var = ExtraVarRefSerializer(required=False, allow_null=True)
    instances = ActivationInstanceSerializer(many=True)
    rules_count = serializers.IntegerField()
    rules_fired_count = serializers.IntegerField()
    restarted_at = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = models.Activation
        fields = [
            "id",
            "name",
            "description",
            "is_enabled",
            "decision_environment",
            "status",
            "git_hash",
            "project",
            "rulebook",
            "extra_var",
            "instances",
            "restart_policy",
            "restart_count",
            "rulebook_name",
            "current_job_id",
            "rules_count",
            "rules_fired_count",
            "created_at",
            "modified_at",
            "restarted_at",
        ]
        read_only_fields = ["id", "created_at", "modified_at", "restarted_at"]

    def to_representation(self, activation):
        decision_environment = (
            DecisionEnvironmentRefSerializer(
                activation["decision_environment"]
            ).data
            if activation["decision_environment"]
            else None
        )
        project = (
            ProjectRefSerializer(activation["project"]).data
            if activation["project"]
            else None
        )
        rulebook = (
            RulebookRefSerializer(activation["rulebook"]).data
            if activation["rulebook"]
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
            "decision_environment": decision_environment,
            "status": activation["status"],
            "git_hash": activation["git_hash"],
            "project": project,
            "rulebook": rulebook,
            "extra_var": extra_var,
            "instances": ActivationInstanceSerializer(
                activation["instances"], many=True
            ).data,
            "restart_policy": activation["restart_policy"],
            "restart_count": activation["restart_count"],
            "rulebook_name": activation["rulebook_name"],
            "current_job_id": activation["current_job_id"],
            "rules_count": activation["rules_count"],
            "rules_fired_count": activation["rules_fired_count"],
            "created_at": activation["created_at"],
            "modified_at": activation["modified_at"],
            "restarted_at": activation["restarted_at"],
        }
