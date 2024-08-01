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

from django.db import models

from .base import BaseOrgModel, UniqueNamedModel

__all__ = ("CredentialType",)


class CredentialType(BaseOrgModel, UniqueNamedModel):
    router_basename = "credentialtype"

    class Meta:
        db_table = "core_credential_type"
        constraints = [
            models.CheckConstraint(
                check=~models.Q(name=""),
                name="ck_empty_credential_type_name",
            )
        ]
        ordering = ("name",)

    description = models.TextField(default="", blank=True, null=False)
    inputs = models.JSONField(default=dict)
    injectors = models.JSONField(default=dict)
    managed = models.BooleanField(default=False)
    kind = models.TextField(default="cloud", blank=True, null=False)
    namespace = models.TextField(default=None, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)
