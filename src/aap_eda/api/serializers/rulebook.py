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


class RulebookSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True,
        help_text="Name of the rulebook",
    )

    path = serializers.CharField(
        required=True, help_text="Relative path of the rulebook"
    )

    description = serializers.CharField(
        default="",
        help_text="Description of the rulebook",
        allow_null=True,
    )

    rulesets = serializers.CharField(
        required=True,
        help_text="The contained rulesets in the rulebook",
    )

    project = serializers.PrimaryKeyRelatedField(
        required=False,
        allow_null=True,
        queryset=models.Project.objects.all(),
        help_text="ID of the project",
    )

    class Meta:
        model = models.Rulebook
        fields = "__all__"
        read_only_fields = ["id", "created_at", "modified_at"]


class RulebookRefSerializer(serializers.ModelSerializer):
    """Serializer for Rulebook reference."""

    class Meta:
        model = models.Rulebook
        fields = ["id", "name", "path", "description"]
        read_only_fields = ["id"]


class RulesetSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True,
        help_text="Name of the ruleset",
    )

    sources = serializers.JSONField(
        required=True,
        help_text="The contained sources in the ruleset",
    )

    class Meta:
        model = models.Ruleset
        fields = "__all__"
        read_only_fields = ["id", "created_at", "modified_at"]


class RulesetOutSerializer(serializers.Serializer):
    id = serializers.IntegerField(
        required=True,
        help_text="ID of the ruleset",
    )

    name = serializers.CharField(
        required=True,
        help_text="Name of the ruleset",
    )

    rule_count = serializers.IntegerField(
        required=True,
        help_text="Number of rules the ruleset contains",
    )

    source_types = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        help_text="List of source types",
    )

    fired_stats = serializers.ListField(
        child=serializers.JSONField(),
        required=True,
        help_text="List of stats",
    )

    created_at = serializers.DateTimeField(
        required=True,
        help_text="The created_at timestamp of the ruleset",
    )

    modified_at = serializers.DateTimeField(
        required=True,
        help_text="The modified_at timestamp of the ruleset",
    )


class RuleSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True,
        help_text="Name of the rule",
    )

    action = serializers.JSONField(
        required=True,
        help_text="The action in the rule",
    )

    class Meta:
        model = models.Rule
        fields = "__all__"
        read_only_fields = ["id", "created_at", "modified_at"]


class RuleOutSerializer(serializers.Serializer):
    id = serializers.IntegerField(
        required=True,
        help_text="ID of the ruleset",
    )

    name = serializers.CharField(
        required=True,
        help_text="Name of the rule",
    )

    action = serializers.JSONField(
        default=dict,
        help_text="The action in the rule",
        allow_null=True,
    )

    fired_stats = serializers.ListField(
        child=serializers.JSONField(),
        required=True,
        help_text="List of stats",
    )

    rulebook = serializers.PrimaryKeyRelatedField(
        required=False,
        allow_null=True,
        queryset=models.Rulebook.objects.all(),
        help_text="ID of the rulebook",
    )

    ruleset = serializers.PrimaryKeyRelatedField(
        required=False,
        allow_null=True,
        queryset=models.Ruleset.objects.all(),
        help_text="ID of the ruleset",
    )

    project = serializers.PrimaryKeyRelatedField(
        required=False,
        allow_null=True,
        queryset=models.Project.objects.all(),
        help_text="ID of the project",
    )


class AuditRuleSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(
        required=True,
        help_text="ID of the fired rule",
    )

    name = serializers.CharField(
        required=False,
        help_text="Name of the fired rule",
    )

    description = serializers.CharField(
        required=False,
        help_text="Description of the fired rule",
    )

    status = serializers.CharField(
        required=False,
        help_text="Status of the fired rule",
    )

    fired_date = serializers.DateTimeField(
        required=True,
        help_text="The fired timestamp of the rule",
    )

    definition = serializers.JSONField(
        required=True,
        help_text="The action in the rule",
    )

    class Meta:
        model = models.AuditRule
        fields = "__all__"
        read_only_fields = ["id", "created_at"]
