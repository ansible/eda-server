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

from django.contrib.contenttypes.models import ContentType
from django.db import models

from aap_eda.core.enums import Action, ResourceType

__all__ = ("Role", "Permission", "DABPermission")


class Role(models.Model):
    class Meta:
        db_table = "core_role"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.TextField(null=False, unique=True)
    description = models.TextField(null=False, default="")
    is_default = models.BooleanField(null=True, default=False)

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


class DABPermission(models.Model):
    """Custom permission model for DAB RBAC.

    This is a partial copy of auth.Permission to be used by DAB RBAC lib
    and in order to be consistent with other applications
    """

    name = models.CharField("name", max_length=255)
    content_type = models.ForeignKey(
        ContentType, models.CASCADE, verbose_name="content type"
    )
    codename = models.CharField("codename", max_length=100)

    class Meta:
        verbose_name = "permission"
        verbose_name_plural = "permissions"
        unique_together = [["content_type", "codename"]]
        ordering = ["content_type__model", "codename"]

    def __str__(self):
        return f"<{self.__class__.__name__}: {self.codename}>"

    def natural_key(self):
        return (self.codename,) + self.content_type.natural_key()

    def get_action(self):
        action, model = self.codename.split("_", 1)
        return action

    def get_model(self):
        action, model = self.codename.split("_", 1)
        return model
