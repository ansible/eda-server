from rest_framework import serializers

from aap_eda.core import models


class ExtraVarSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ExtraVar
        fields = "__all__"


class PlaybookSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Playbook
        fields = "__all__"
