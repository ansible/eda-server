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

import datetime
import logging

from django.db import models
from django.utils import timezone

from aap_eda.core.utils.crypto.fields import EncryptedTextField

from .base import BaseOrgModel, PrimordialModel, UniqueNamedModel

logger = logging.getLogger(__name__)

PROJECT_ARCHIVE_DIR = "projects/"


class Project(BaseOrgModel, UniqueNamedModel, PrimordialModel):
    # Grace period to prevent infinite sync->restart->sync cycles
    SYNC_GRACE_PERIOD_SECONDS = 30

    class Meta:
        db_table = "core_project"
        constraints = [
            models.CheckConstraint(
                check=~models.Q(name=""),
                name="ck_empty_project_name",
            ),
            models.CheckConstraint(
                check=models.Q(scm_update_cache_timeout__range=(0, 86400)),
                name="ck_cache_timeout_range",
            ),
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

    # Project Auto-Sync Configuration Fields
    update_revision_on_launch = models.BooleanField(
        default=False,
        help_text="Enable automatic project sync on activation launch",
    )
    scm_update_cache_timeout = models.IntegerField(
        default=0,
        help_text=(
            "Cache timeout in seconds for project updates"
            " (0 = always update, max 86400)"
        ),
    )
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        help_text="Timestamp of the last successful project sync",
    )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id}, name={self.name})>"

    @property
    def needs_update_on_launch(self) -> bool:
        """
        Determine if project needs to be updated on activation launch.

        Returns False if update_revision_on_launch is disabled.
        Returns False if within SYNC_GRACE_PERIOD_SECONDS of last sync.
        Returns False if cache timeout hasn't expired.
        Returns True otherwise.

        The grace period prevents infinite loops when
        restart_on_project_update=True on activations, even if
        scm_update_cache_timeout=0 (always update).
        """
        try:
            if not self.update_revision_on_launch:
                return False

            current_time = timezone.now()

            # Apply grace period to prevent infinite restart loops
            if self.last_synced_at is not None:
                grace_expiry = self.last_synced_at + datetime.timedelta(
                    seconds=self.SYNC_GRACE_PERIOD_SECONDS
                )
                if current_time <= grace_expiry:
                    return False

            # If cache timeout is 0, always update (after grace period)
            if self.scm_update_cache_timeout == 0:
                return True

            # If never synced, update is needed
            if self.last_synced_at is None:
                return True

            # Check if cache timeout has expired
            cache_expiry = self.last_synced_at + datetime.timedelta(
                seconds=self.scm_update_cache_timeout
            )
            return current_time > cache_expiry

        except (AttributeError, TypeError, ValueError) as e:
            # Log error but return safe default to prevent activation failures
            logger.error(
                f"Error determining sync status for project {self.pk}: {e}"
            )
            # Safe default: assume sync needed to prevent stale content
            return True


__all__ = [
    "Project",
]
