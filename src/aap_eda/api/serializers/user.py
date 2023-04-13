from rest_framework import serializers

from aap_eda.core import models

from .auth import RoleRefSerializer


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_superuser",
            "roles",
            "date_joined",
            "modified_at",
        ]


class UserListSerializer(serializers.Serializer):
    id = serializers.IntegerField(
        required=True, help_text="The ID of the user"
    )

    username = serializers.CharField(
        required=True,
        help_text="The user's log in name.",
    )

    first_name = serializers.CharField(
        required=True,
        help_text="The user's first name.",
    )

    last_name = serializers.CharField(
        required=True,
        help_text="The user's last name.",
    )

    is_superuser = serializers.BooleanField(
        required=True, help_text="The user's type."
    )

    roles = RoleRefSerializer(read_only=True, many=True)


class UserCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "password",
            "roles",
            "is_superuser",
        ]


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


class AwxTokenListSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AwxToken
        fields = ["id", "name", "description", "token"]
        read_only_fields = ["id", "name", "descritption", "token"]
