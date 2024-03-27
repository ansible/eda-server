from django.contrib.auth.hashers import make_password
from rest_framework import serializers

from aap_eda.core import models

from .auth import RoleRefSerializer


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.User
        fields = "__all__"


class UserDetailSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        help_text="The user's log in name.",
    )
    created_at = serializers.DateTimeField(source="date_joined")

    roles = RoleRefSerializer(
        many=True, allow_empty=True, allow_null=True, required=False
    )

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
            "created_at",
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
        required=True,
        help_text="The user is a superuser.",
    )

    roles = RoleRefSerializer(
        many=True, allow_empty=True, allow_null=True, required=False
    )


class UserUpdateSerializerBase(serializers.ModelSerializer):
    username = serializers.CharField(
        help_text="The user's log in name.",
    )
    password = serializers.CharField(write_only=True)

    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data["password"] = make_password(password)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        if password:
            validated_data["password"] = make_password(password)
        return super().update(instance, validated_data)


class UserCreateUpdateSerializer(UserUpdateSerializerBase):
    class Meta:
        model = models.User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "password",
            "is_superuser",
            "roles",
        ]


class CurrentUserUpdateSerializer(UserUpdateSerializerBase):
    class Meta:
        model = models.User
        fields = [
            "first_name",
            "last_name",
            "email",
            "password",
        ]


class AwxTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AwxToken
        fields = [
            "id",
            "name",
            "description",
            "user_id",
            "created_at",
            "modified_at",
        ]


class AwxTokenCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AwxToken
        fields = [
            "name",
            "description",
            "token",
        ]
