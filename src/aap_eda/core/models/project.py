#  Copyright 2022-2023 Red Hat, Inc.
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

from .base import BaseOrgModel, UniqueNamedModel

PROJECT_ARCHIVE_DIR = "projects/"


class Project(BaseOrgModel, UniqueNamedModel):
    class Meta:
        db_table = "core_project"
        constraints = [
            models.CheckConstraint(
                check=~models.Q(name=""),
                name="ck_empty_project_name",
            )
        ]
        permissions = [
            ("sync_project", "Can sync a project"),
        ]

    class ImportState(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        FAILED = "failed"
        COMPLETED = "completed"

    class ScmType(models.TextChoices):
        GIT = "git"

    description = models.TextField(default="", blank=True, null=False)
    url = models.TextField(null=False)
    proxy = EncryptedTextField(blank=True, default="")
    git_hash = models.TextField()
    verify_ssl = models.BooleanField(default=True)
    # TODO: used by migration, remove it later
    credential = models.ForeignKey(
        "Credential",
        blank=True,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
    )
    eda_credential = models.ForeignKey(
        "EdaCredential",
        blank=True,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
    )
    archive_file = models.FileField(upload_to=PROJECT_ARCHIVE_DIR)

    import_state = models.TextField(
        choices=ImportState.choices, default=ImportState.PENDING, null=False
    )
    import_task_id = models.UUIDField(null=True, default=None)
    import_error = models.TextField(null=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)

    scm_type = models.TextField(
        choices=ScmType.choices,
        default=ScmType.GIT,
    )
    scm_branch = models.TextField(blank=True, default="")
    scm_refspec = models.TextField(blank=True, default="")

    # credential (keys) used to validate content signature
    signature_validation_credential = models.ForeignKey(
        "EdaCredential",
        related_name="%(class)ss_signature_validation",
        blank=True,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
    )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id}, name={self.name})>"


__all__ = [
    "Project",
]
