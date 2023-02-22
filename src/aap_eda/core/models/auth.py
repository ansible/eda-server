#  Copyright 2022 Red Hat, Inc.
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

import uuid

from django.db import models

from aap_eda.core.enums import Action, ResourceType

__all__ = (
    "Role",
    "UserRole",
    "RolePermission",
)


class Role(models.Model):
    class Meta:
        db_table = "core_role"

    role_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.TextField(null=False, unique=True)
    description = models.TextField(null=False, default="")
    is_default = models.BooleanField(null=True, default=False)


class UserRole(models.Model):
    class Meta:
        db_table = "core_user_role"
        unique_together = ["user", "role"]

    user = models.ForeignKey("User", on_delete=models.CASCADE)
    role = models.ForeignKey("Role", on_delete=models.CASCADE)


class RolePermission(models.Model):
    class Meta:
        db_table = "core_role_permission"
        unique_together = ["role", "resource_type", "action"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(resource_type__in=ResourceType.values()),
                name="ck_resource_type_values",
            ),
            models.CheckConstraint(
                check=models.Q(action__in=Action.values()),
                name="ck_action_values",
            ),
        ]
        indexes = [
            models.Index(
                fields=["resource_type", "action"],
                name="ix_role_perm_rsrc_typ_act",
            ),
        ]

    role_permission_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    role = models.ForeignKey("Role", on_delete=models.CASCADE)
    resource_type = models.TextField(
        db_column="resource_type_enum",
        choices=ResourceType.choices(),
        null=False,
    )
    action = models.TextField(
        db_column="action_enum", choices=Action.choices(), null=False
    )
