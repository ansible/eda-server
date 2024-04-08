from django.contrib.auth.hashers import make_password
from rest_framework import serializers

from aap_eda.api.exceptions import Conflict
from aap_eda.core import models


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.User
        fields = "__all__"


class UserDetailSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        help_text="The user's log in name.",
    )
    created_at = serializers.DateTimeField(source="date_joined")

    class Meta:
        model = models.User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_superuser",
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

    def validate(self, data):
        """Validate the uniqueness of a combination of user and name fields."""
        user = self.context["request"].user
        name = data.get("name")

        existing_token = models.AwxToken.objects.filter(user=user, name=name)

        # If updating, exclude the current instance from the queryset
        if self.instance:
            existing_token = existing_token.exclude(pk=self.instance.pk)

        if existing_token.exists():
            raise Conflict("Token with this name already exists.")

        return data
