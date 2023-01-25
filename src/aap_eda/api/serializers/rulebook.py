import yaml
from rest_framework import serializers

from aap_eda.api.services import RulebookService
from aap_eda.core import models


class RulebookSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True,
        help_text="Name of the rulebook",
    )

    description = serializers.CharField(
        default="",
        help_text="Description of the rulebook",
        allow_null=True,
    )

    rulesets = serializers.CharField(
        default="",
        help_text="The contained rulesets in the rulebook",
        allow_null=True,
    )

    project = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID of the project",
    )

    class Meta:
        model = models.Rulebook
        fields = "__all__"
        read_only_fields = ["id", "created_at", "modified_at"]

    def create(self, validated_data):
        rulebook_data = validated_data["rulesets"]
        rulebook = models.Rulebook.objects.create(**validated_data)

        RulebookService(rulebook).insert_rulebook_related_data(
            yaml.safe_load(rulebook_data)
        )

        return rulebook


class RulesetSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True,
        help_text="Name of the ruleset",
    )

    sources = serializers.JSONField(
        default=dict,
        help_text="The contained sources in the ruleset",
        allow_null=True,
    )

    rulebook = serializers.IntegerField(
        required=True, help_text="ID of the rulebook"
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
