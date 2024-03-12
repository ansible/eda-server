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

from aap_eda.api.serializers.credential import CredentialSerializer
from aap_eda.api.serializers.decision_environment import (
    DecisionEnvironmentRefSerializer,
)
from aap_eda.api.serializers.organization import OrganizationRefSerializer
from aap_eda.api.serializers.project import (
    ExtraVarRefSerializer,
    ProjectRefSerializer,
)
from aap_eda.api.serializers.rulebook import RulebookRefSerializer
from aap_eda.core import models, validators


class ActivationSerializer(serializers.ModelSerializer):
    """Serializer for the Activation model."""

    credentials = serializers.ListField(
        required=False,
        allow_null=True,
        child=CredentialSerializer(),
    )

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
            "organization_id",
            "restart_policy",
            "restart_count",
            "rulebook_name",
            "ruleset_stats",
            "current_job_id",
            "created_at",
            "modified_at",
            "status_message",
            "awx_token_id",
            "credentials",
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
    credentials = serializers.ListField(
        required=False,
        allow_null=True,
        child=CredentialSerializer(),
    )

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
            "organization_id",
            "restart_policy",
            "restart_count",
            "rulebook_name",
            "current_job_id",
            "rules_count",
            "rules_fired_count",
            "created_at",
            "modified_at",
            "status_message",
            "awx_token_id",
            "credentials",
        ]
        read_only_fields = ["id", "created_at", "modified_at"]

    def to_representation(self, activation):
        rules_count, rules_fired_count = get_rules_count(
            activation.ruleset_stats
        )
        credentials = [
            CredentialSerializer(credential).data
            for credential in activation.credentials.all()
        ]

        return {
            "id": activation.id,
            "name": activation.name,
            "description": activation.description,
            "is_enabled": activation.is_enabled,
            "status": activation.status,
            "decision_environment_id": activation.decision_environment_id,
            "project_id": activation.project_id,
            "rulebook_id": activation.rulebook_id,
            "extra_var_id": activation.extra_var_id,
            "organization_id": activation.organization_id,
            "restart_policy": activation.restart_policy,
            "restart_count": activation.restart_count,
            "rulebook_name": activation.rulebook_name,
            "current_job_id": activation.current_job_id,
            "rules_count": rules_count,
            "rules_fired_count": rules_fired_count,
            "created_at": activation.created_at,
            "modified_at": activation.modified_at,
            "status_message": activation.status_message,
            "awx_token_id": activation.awx_token_id,
            "credentials": credentials,
        }


class ActivationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating the Activation."""

    organization_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = models.Activation
        fields = [
            "name",
            "description",
            "is_enabled",
            "decision_environment_id",
            "rulebook_id",
            "extra_var_id",
            "organization_id",
            "user",
            "restart_policy",
            "awx_token_id",
            "credentials",
        ]

    rulebook_id = serializers.IntegerField(
        validators=[validators.check_if_rulebook_exists]
    )
    extra_var_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        validators=[validators.check_if_extra_var_exists],
    )
    decision_environment_id = serializers.IntegerField(
        validators=[validators.check_if_de_exists]
    )
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    awx_token_id = serializers.IntegerField(
        allow_null=True,
        validators=[validators.check_if_awx_token_exists],
        required=False,
    )
    credentials = serializers.ListField(
        required=False,
        allow_null=True,
        child=serializers.IntegerField(),
    )

    def validate(self, data):
        user = data["user"]
        awx_token = models.AwxToken.objects.filter(
            id=data.get("awx_token_id"),
        ).first()
        if awx_token and awx_token.user != user:
            raise serializers.ValidationError(
                "The Awx Token does not belong to the user."
            )
        if not awx_token:
            validate_rulebook_token(data["rulebook_id"])

        return data

    def create(self, validated_data):
        rulebook_id = validated_data["rulebook_id"]
        rulebook = models.Rulebook.objects.get(id=rulebook_id)
        validated_data["user_id"] = validated_data["user"].id
        validated_data["rulebook_name"] = rulebook.name
        validated_data["rulebook_rulesets"] = rulebook.rulesets
        validated_data["git_hash"] = rulebook.project.git_hash
        validated_data["project_id"] = rulebook.project.id
        return super().create(validated_data)


class ActivationInstanceSerializer(serializers.ModelSerializer):
    """Serializer for the Activation Instance model."""

    class Meta:
        model = models.RulebookProcess
        fields = [
            "id",
            "name",
            "status",
            "git_hash",
            "status_message",
            "activation_id",
            "started_at",
            "ended_at",
        ]
        read_only_fields = ["id", "started_at", "ended_at"]


class ActivationInstanceLogSerializer(serializers.ModelSerializer):
    """Serializer for the Activation Instance Log model."""

    class Meta:
        model = models.RulebookProcessLog
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
    organization = OrganizationRefSerializer()
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
            "organization",
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
            "status_message",
            "awx_token_id",
            "credentials",
        ]
        read_only_fields = ["id", "created_at", "modified_at", "restarted_at"]

    def to_representation(self, activation):
        decision_environment = (
            DecisionEnvironmentRefSerializer(
                activation.decision_environment
            ).data
            if activation.decision_environment
            else None
        )
        project = (
            ProjectRefSerializer(activation.project).data
            if activation.project
            else None
        )
        rulebook = (
            RulebookRefSerializer(activation.rulebook).data
            if activation.rulebook
            else None
        )
        extra_var = (
            ExtraVarRefSerializer(activation.extra_var).data
            if activation.extra_var
            else None
        )
        activation_instances = models.RulebookProcess.objects.filter(
            activation_id=activation.id
        )
        rules_count, rules_fired_count = get_rules_count(
            activation.ruleset_stats
        )
        # restart_count can be zero even if there are more than one instance
        # because it is incremented only when the activation
        # is restarted automatically
        restarted_at = (
            activation_instances.latest("started_at").started_at
            if len(activation_instances) > 1 and activation.restart_count > 0
            else None
        )
        credentials = [
            CredentialSerializer(credential).data
            for credential in activation.credentials.all()
        ]
        organization = (
            OrganizationRefSerializer(activation.organization).data
            if activation.organization
            else None
        )

        return {
            "id": activation.id,
            "name": activation.name,
            "description": activation.description,
            "is_enabled": activation.is_enabled,
            "decision_environment": decision_environment,
            "status": activation.status,
            "git_hash": activation.git_hash,
            "project": project,
            "rulebook": rulebook,
            "extra_var": extra_var,
            "organization": organization,
            "instances": ActivationInstanceSerializer(
                activation_instances, many=True
            ).data,
            "restart_policy": activation.restart_policy,
            "restart_count": activation.restart_count,
            "rulebook_name": activation.rulebook_name,
            "current_job_id": activation.current_job_id,
            "rules_count": rules_count,
            "rules_fired_count": rules_fired_count,
            "created_at": activation.created_at,
            "modified_at": activation.modified_at,
            "restarted_at": restarted_at,
            "status_message": activation.status_message,
            "awx_token_id": activation.awx_token_id,
            "credentials": credentials,
        }


class PostActivationSerializer(serializers.ModelSerializer):
    """Serializer for validating activations before reactivate them."""

    name = serializers.CharField(required=True)
    decision_environment_id = serializers.IntegerField(
        validators=[validators.check_if_de_exists]
    )
    extra_var_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        validators=[validators.check_if_extra_var_exists],
    )
    awx_token_id = serializers.IntegerField(
        allow_null=True,
        validators=[validators.check_if_awx_token_exists],
    )
    rulebook_id = serializers.IntegerField(allow_null=True)

    def validate(self, data):
        awx_token = data.get("awx_token_id")

        if not awx_token:
            validate_rulebook_token(data["rulebook_id"])

        return data

    class Meta:
        model = models.Activation
        fields = [
            "id",
            "name",
            "status",
            "decision_environment_id",
            "extra_var_id",
            "organization_id",
            "user_id",
            "created_at",
            "modified_at",
            "awx_token_id",
            "rulebook_id",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
        ]


def get_rules_count(ruleset_stats: dict) -> tuple[int, int]:
    rules_count = 0
    rules_fired_count = 0

    # TODO: add schema for validating ruleset_stats
    for ruleset_stat in ruleset_stats.values():
        rules_count += ruleset_stat.get("numberOfRules", 0)
        rules_fired_count += ruleset_stat.get("rulesTriggered", 0)

    return rules_count, rules_fired_count


def is_activation_valid(activation: models.Activation) -> tuple[bool, str]:
    serializer = PostActivationSerializer(data=activation.__dict__)

    valid = serializer.is_valid()
    message = parse_validation_errors(serializer.errors)

    return valid, message


def parse_validation_errors(errors: dict) -> str:
    messages = {key: str(error[0]) for key, error in errors.items() if error}

    return str(messages)


def validate_rulebook_token(rulebook_id: int) -> None:
    """Validate if the rulebook requires an Awx Token."""
    rulebook = models.Rulebook.objects.get(id=rulebook_id)

    # TODO: rulesets are stored as a string in the rulebook model
    # proper instrospection should require a validation of the
    # rulesets. https://issues.redhat.com/browse/AAP-19202
    try:
        rulesets_data = rulebook.get_rulesets_data()
    except ValueError:
        raise serializers.ValidationError("Invalid rulebook data.")

    if validators.check_rulesets_require_token(
        rulesets_data,
    ):
        raise serializers.ValidationError(
            "The rulebook requires an Awx Token.",
        )
