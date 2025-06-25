#  Copyright 2025 Red Hat, Inc.
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

from aap_eda.core.utils.crypto.fields import EncryptedTextField

from .base import BaseOrgModel, PrimordialModel

__all__ = ("CredentialInputSource",)


class CredentialInputSource(BaseOrgModel, PrimordialModel):
    class Meta:
        db_table = "core_credential_input_source"
        unique_together = (("target_credential", "input_field_name"),)
        ordering = (
            "target_credential",
            "source_credential",
            "input_field_name",
        )

    description = models.TextField(default="", blank=True, null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)
    target_credential = models.ForeignKey(
        "EdaCredential",
        related_name="input_sources",
        on_delete=models.CASCADE,
        null=True,
        help_text="Non external credential",
    )
    source_credential = models.ForeignKey(
        "EdaCredential",
        related_name="target_input_sources",
        on_delete=models.CASCADE,
        null=True,
        help_text="External credential",
    )
    input_field_name = models.CharField(
        max_length=1024,
    )

    metadata = EncryptedTextField(default="", blank=True, null=False)
