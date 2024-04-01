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


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(
        required=True, style={"input_type": "password"}
    )


# -----------------------------------------------------
# Permissions
# -----------------------------------------------------
class PermissionSerializer(serializers.ModelSerializer):
    resource_type = serializers.CharField(
        required=True,
        help_text="Resource type of the permission",
    )

    action = serializers.CharField(
        required=True,
        help_text="Action granted by the permission.",
    )

    class Meta:
        model = models.Permission
        fields = "__all__"
        read_only_fields = ["id"]


class PermissionRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Permission
        fields = ["resource_type", "action"]
        read_only_fields = ["resource_type", "action"]


# -----------------------------------------------------
# Roles
# -----------------------------------------------------
class RoleSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(
        required=True, help_text="Unique UUID of the role"
    )

    name = serializers.CharField(
        required=True,
        help_text="Name of the rulebook",
    )

    description = serializers.CharField(
        default="",
        help_text="Description of the rulebook",
        allow_null=True,
    )

    is_default = serializers.BooleanField(
        default=False, help_text="Indicates if the role is default"
    )

    class Meta:
        model = models.Role
        fields = "__all__"
        read_only_fields = ["created_at", "modified_at"]


class RoleListSerializer(serializers.Serializer):
    id = serializers.UUIDField(
        required=True, help_text="Unique UUID of the role"
    )

    name = serializers.CharField(
        required=True,
        help_text="Name of the rulebook",
    )

    description = serializers.CharField(
        default="",
        help_text="Description of the rulebook",
        allow_null=True,
    )


class RoleDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField(
        required=True, help_text="Unique UUID of the role"
    )

    name = serializers.CharField(
        required=True,
        help_text="Name of the role",
    )

    description = serializers.CharField(
        default="",
        help_text="Description of the role",
        allow_null=True,
    )

    permissions = PermissionRefSerializer(read_only=True, many=True)

    created_at = serializers.DateTimeField(
        required=True,
        help_text="The created_at timestamp of the role",
    )

    modified_at = serializers.DateTimeField(
        required=True,
        help_text="The modified_at timestamp of the role",
    )


class RoleRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Role
        fields = ["id", "name"]
        read_only_fields = ["id", "name"]
