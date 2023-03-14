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

PROJECT_ARCHIVE_DIR = "projects/"


class Project(models.Model):
    class Meta:
        db_table = "core_project"
        constraints = [
            models.CheckConstraint(
                check=~models.Q(name=""),
                name="ck_empty_project_name",
            )
        ]

    class ImportState(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        FAILED = "failed"
        COMPLETED = "completed"

    name = models.TextField(null=False, unique=True)
    description = models.TextField(default="", blank=True, null=False)
    url = models.TextField(null=False)
    git_hash = models.TextField()
    archive_file = models.FileField(upload_to=PROJECT_ARCHIVE_DIR)

    import_state = models.TextField(
        choices=ImportState.choices, default=ImportState.PENDING, null=False
    )
    import_task_id = models.UUIDField(null=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id}, name={self.name})>"


class Playbook(models.Model):
    class Meta:
        db_table = "core_playbook"

    name = models.TextField(unique=True)
    playbook = models.TextField()
    project = models.ForeignKey("Project", on_delete=models.CASCADE, null=True)


class ExtraVar(models.Model):
    class Meta:
        db_table = "core_extra_var"

    name = models.TextField(unique=True)
    extra_var = models.TextField()
    project = models.ForeignKey("Project", on_delete=models.CASCADE, null=True)


__all__ = [
    "ExtraVar",
    "Playbook",
    "Project",
]
