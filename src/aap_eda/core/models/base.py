#  Copyright 2024 Red Hat, Inc.
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

from crum import get_current_user
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import models

__all__ = ("BaseOrgModel", "UniqueNamedModel", "PrimordialModel")

User = get_user_model()


class BaseOrgModel(models.Model):
    class Meta:
        abstract = True

    organization = models.ForeignKey(
        "Organization",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )


class UniqueNamedModel(models.Model):
    class Meta:
        abstract = True

    name = models.TextField(null=False, unique=True)

    def summary_fields(self):
        return {
            "id": self.id,
            "name": self.name,
        }


class PrimordialModel(models.Model):
    """Basic model with common created_by and modified_by fields."""

    class Meta:
        abstract = True

    created_by = models.ForeignKey(
        User,
        related_name="%s(class)s_created+",
        default=None,
        null=True,
        editable=False,
        on_delete=models.SET_NULL,
    )
    modified_by = models.ForeignKey(
        User,
        related_name="%s(class)s_modified+",
        default=None,
        null=True,
        editable=False,
        on_delete=models.SET_NULL,
    )

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields", [])
        current_user = get_current_user()
        if current_user:
            if isinstance(current_user, AnonymousUser):
                super().save(*args, **kwargs)
                return

            # Set `created_by` only for new objects
            if not self.pk and not self.created_by:
                self.created_by = current_user
                if "created_by" not in update_fields:
                    update_fields.append("created_by")

            # Always update `modified_by`
            self.modified_by = current_user
            if "modified_by" not in update_fields:
                update_fields.append("modified_by")

        super().save(*args, **kwargs)
