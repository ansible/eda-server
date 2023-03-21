from rest_framework import serializers

from aap_eda.core import models


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.User
        fields = ["username", "email", "first_name", "last_name"]
        read_only_fields = ["username"]


class AwxTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AwxToken
        fields = [
            "id",
            "name",
            "description",
            "token",
            "user",
            "created_at",
            "modified_at",
        ]
        read_only_fields = ["id", "user", "created_at", "modified_at"]
        extra_kwargs = {"token": {"write_only": True}}
