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

from django.db import models

from aap_eda.core.enums import CredentialType
from aap_eda.core.utils.crypto.fields import EncryptedTextField

__all__ = ("Credential",)


class Credential(models.Model):
    class Meta:
        db_table = "core_credential"
        constraints = [
            models.CheckConstraint(
                check=~models.Q(name=""),
                name="ck_empty_credential_name",
            )
        ]

    name = models.TextField(null=False, unique=True)
    description = models.TextField(default="", blank=True, null=False)
    credential_type = models.TextField(
        choices=CredentialType.choices(),
        default=CredentialType.REGISTRY,
    )
    username = models.TextField(null=True)
    secret = EncryptedTextField(null=False)
    key = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)
