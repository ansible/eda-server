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
    "Permission",
)


class Role(models.Model):
    class Meta:
        db_table = "core_role"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.TextField(null=False, unique=True)
    description = models.TextField(null=False, default="")
    is_default = models.BooleanField(null=True, default=False)
    organization = models.ForeignKey(
        "Organization", on_delete=models.CASCADE, null=True
    )

    permissions = models.ManyToManyField("Permission", related_name="roles")
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"


class Permission(models.Model):
    """Available permissions.

    This model describes all available permissions. A permission is a pair
    of resource and action.
    """

    class Meta:
        db_table = "core_permission"
        unique_together = [("resource_type", "action")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    resource_type = models.TextField(
        null=False, blank=False, choices=ResourceType.choices()
    )
    action = models.TextField(
        null=False, blank=False, choices=Action.choices()
    )

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}: {self.resource_type}:{self.action}>"
        )
