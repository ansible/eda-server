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
import datetime

from ansible_base.rbac.models import DABPermission, RoleDefinition
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
    class Meta:
        model = models.Permission
        fields = "__all__"
        read_only_fields = ["id"]

    resource_type = serializers.SerializerMethodField()
    action = serializers.SerializerMethodField()

    def get_resource_type(self, obj) -> str:
        action, model = obj.codename.split("_", 1)
        return model

    def get_action(self, obj) -> str:
        action, model = obj.codename.split("_", 1)
        return action


class PermissionRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = DABPermission
        fields = ["resource_type", "action"]
        read_only_fields = ["resource_type", "action"]

    resource_type = serializers.SerializerMethodField()
    action = serializers.SerializerMethodField()

    def get_resource_type(self, obj) -> str:
        action, model = obj.codename.split("_", 1)
        return model

    def get_action(self, obj) -> str:
        action, model = obj.codename.split("_", 1)
        return action


# -----------------------------------------------------
# Roles
# -----------------------------------------------------
class RoleSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(
        required=True, help_text="Unique id of the role"
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
    created_at = serializers.SerializerMethodField()
    modified_at = serializers.SerializerMethodField()

    def get_created_at(self, obj) -> datetime.datetime:
        return obj.created

    def get_modified_at(self, obj) -> datetime.datetime:
        return obj.modified

    class Meta:
        model = RoleDefinition
        fields = "__all__"


class RoleListSerializer(serializers.Serializer):
    id = serializers.IntegerField(
        required=True, help_text="Unique id of the role"
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
    id = serializers.IntegerField(
        required=True, help_text="Unique id of the role"
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

    created_at = serializers.SerializerMethodField()
    modified_at = serializers.SerializerMethodField()

    def get_created_at(self, obj) -> datetime.datetime:
        return obj.created

    def get_modified_at(self, obj) -> datetime.datetime:
        return obj.modified


class RoleRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoleDefinition
        fields = ["id", "name"]
        read_only_fields = ["id", "name"]
