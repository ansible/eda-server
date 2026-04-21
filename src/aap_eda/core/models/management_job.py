#  Copyright 2026 Red Hat, Inc.
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

from aap_eda.core.enums import ExecutionStatus, ManagementJobType

from .base import BaseOrgModel, UniqueNamedModel

__all__ = (
    "ManagementJob",
    "ManagementJobSchedule",
    "ManagementJobExecution",
)


class ManagementJob(BaseOrgModel, UniqueNamedModel):
    class Meta:
        db_table = "core_management_job"
        ordering = ("-created_at",)

    description = models.TextField(default="", blank=True)
    job_type = models.TextField(
        choices=ManagementJobType.choices(),
        default=ManagementJobType.CLEANUP_AUDIT_LOGS,
    )
    is_enabled = models.BooleanField(default=True)
    parameters = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)


class ManagementJobSchedule(BaseOrgModel):
    class Meta:
        db_table = "core_management_job_schedule"
        ordering = ("-next_run_at",)

    management_job = models.ForeignKey(
        ManagementJob,
        on_delete=models.CASCADE,
        related_name="schedules",
    )
    schedule = models.TextField(help_text="Cron expression")
    next_run_at = models.DateTimeField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)


class ManagementJobExecution(BaseOrgModel):
    class Meta:
        db_table = "core_management_job_execution"
        ordering = ("-started_at",)

    management_job = models.ForeignKey(
        ManagementJob,
        on_delete=models.CASCADE,
        related_name="executions",
    )
    status = models.TextField(
        choices=ExecutionStatus.choices(),
        default=ExecutionStatus.PENDING,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    output = models.TextField(default="", blank=True)
    errors = models.TextField(default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
