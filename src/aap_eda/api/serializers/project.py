from rest_framework import serializers

from aap_eda.core import models


class ExtraVarSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True,
        help_text="Name of the extra_var",
    )

    extra_var = serializers.CharField(
        required=True,
        help_text="Content of the extra_var",
    )

    class Meta:
        model = models.ExtraVar
        fields = "__all__"
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
