from rest_framework import serializers

from aap_eda.api.serializers import ExtraVarSerializer
from aap_eda.core import models


class ActivationSerializer(serializers.ModelSerializer):
    """Serializer for the Activation model."""

    name = serializers.CharField(required=True)
    description = serializers.CharField(required=False)
    is_enabled = serializers.BooleanField(required=True)
    working_directory = serializers.CharField(required=False)
    execution_environment = serializers.CharField(required=True)
    project = serializers.CharField(required=True)
    rulebook = serializers.CharField(required=True)
    inventory = serializers.CharField(required=True)
    extra_var = ExtraVarSerializer(required=True)
    restart_policy = serializers.CharField(required=True)
    restart_count = serializers.IntegerField(required=True)
    created_at = serializers.DateTimeField(required=True)
    modified_at = serializers.DateTimeField(required=True)

    class Meta:
        model = models.Activation
        fields = "__all__"
        read_only_fields = ["id"]


class ActivationInstanceSerializer(serializers.ModelSerializer):
    """Serializer for the Activation Instance model."""

    name = serializers.CharField(required=True)
    status = serializers.CharField(required=True)
    started_at = serializers.DateTimeField(required=True)
    ended_at = serializers.DateTimeField(required=False)
    activation = ActivationSerializer(required=True)

    class Meta:
        model = models.ActivationInstance
        fields = "__all__"
        read_only_fields = ["id"]
