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

import pytest
from django.db import IntegrityError
from django.utils import timezone

from aap_eda.core.enums import ExecutionStatus, ManagementJobType
from aap_eda.core.models import (
    ManagementJob,
    ManagementJobExecution,
    ManagementJobSchedule,
)


@pytest.fixture()
def management_job(default_organization):
    return ManagementJob.objects.create(
        name="Cleanup Audit Logs",
        description="Remove old audit rule logs",
        job_type=ManagementJobType.CLEANUP_AUDIT_LOGS,
        is_enabled=True,
        parameters={"retention_days": 90},
        organization=default_organization,
    )


@pytest.fixture()
def management_job_schedule(management_job, default_organization):
    return ManagementJobSchedule.objects.create(
        management_job=management_job,
        schedule="0 2 * * *",
        is_enabled=True,
        organization=default_organization,
    )


@pytest.fixture()
def management_job_execution(management_job, default_organization):
    return ManagementJobExecution.objects.create(
        management_job=management_job,
        status=ExecutionStatus.PENDING,
        organization=default_organization,
    )


# -- ManagementJob model tests --


@pytest.mark.django_db
def test_create_management_job(management_job):
    assert management_job.pk is not None
    assert management_job.name == "Cleanup Audit Logs"
    assert management_job.description == "Remove old audit rule logs"
    assert management_job.job_type == ManagementJobType.CLEANUP_AUDIT_LOGS
    assert management_job.is_enabled is True
    assert management_job.parameters == {"retention_days": 90}
    assert management_job.created_at is not None
    assert management_job.modified_at is not None


@pytest.mark.django_db
def test_management_job_unique_name(management_job, default_organization):
    with pytest.raises(IntegrityError):
        ManagementJob.objects.create(
            name="Cleanup Audit Logs",
            job_type=ManagementJobType.CLEANUP_STALE_ACTIVATIONS,
            organization=default_organization,
        )


@pytest.mark.django_db
def test_management_job_default_values(default_organization):
    job = ManagementJob.objects.create(
        name="Default Job",
        organization=default_organization,
    )
    assert job.is_enabled is True
    assert job.description == ""
    assert job.parameters == {}
    assert job.job_type == ManagementJobType.CLEANUP_AUDIT_LOGS


@pytest.mark.django_db
def test_management_job_types():
    assert ManagementJobType.CLEANUP_AUDIT_LOGS == "cleanup_audit_logs"
    assert ManagementJobType.CLEANUP_STALE_ACTIVATIONS == (
        "cleanup_stale_activations"
    )


# -- ManagementJobSchedule model tests --


@pytest.mark.django_db
def test_create_management_job_schedule(management_job_schedule):
    assert management_job_schedule.pk is not None
    assert management_job_schedule.schedule == "0 2 * * *"
    assert management_job_schedule.is_enabled is True
    assert management_job_schedule.next_run_at is None
    assert management_job_schedule.last_run_at is None
    assert management_job_schedule.created_at is not None
    assert management_job_schedule.modified_at is not None


@pytest.mark.django_db
def test_schedule_belongs_to_job(management_job, management_job_schedule):
    assert management_job_schedule.management_job == management_job
    assert management_job.schedules.count() == 1
    assert management_job.schedules.first() == management_job_schedule


@pytest.mark.django_db
def test_schedule_timestamps(management_job_schedule):
    now = timezone.now()
    management_job_schedule.next_run_at = now
    management_job_schedule.last_run_at = now
    management_job_schedule.save()
    management_job_schedule.refresh_from_db()
    assert management_job_schedule.next_run_at is not None
    assert management_job_schedule.last_run_at is not None


# -- ManagementJobExecution model tests --


@pytest.mark.django_db
def test_create_management_job_execution(management_job_execution):
    assert management_job_execution.pk is not None
    assert management_job_execution.status == ExecutionStatus.PENDING
    assert management_job_execution.started_at is None
    assert management_job_execution.finished_at is None
    assert management_job_execution.output == ""
    assert management_job_execution.errors == ""
    assert management_job_execution.created_at is not None


@pytest.mark.django_db
def test_execution_belongs_to_job(management_job, management_job_execution):
    assert management_job_execution.management_job == management_job
    assert management_job.executions.count() == 1
    assert management_job.executions.first() == management_job_execution


@pytest.mark.django_db
def test_execution_status_transitions(management_job_execution):
    now = timezone.now()

    management_job_execution.status = ExecutionStatus.RUNNING
    management_job_execution.started_at = now
    management_job_execution.save()
    management_job_execution.refresh_from_db()
    assert management_job_execution.status == ExecutionStatus.RUNNING

    management_job_execution.status = ExecutionStatus.COMPLETED
    management_job_execution.finished_at = now
    management_job_execution.output = "Deleted 150 records"
    management_job_execution.save()
    management_job_execution.refresh_from_db()
    assert management_job_execution.status == ExecutionStatus.COMPLETED
    assert management_job_execution.output == "Deleted 150 records"


@pytest.mark.django_db
def test_execution_failed_status(management_job_execution):
    management_job_execution.status = ExecutionStatus.FAILED
    management_job_execution.errors = "Database connection timeout"
    management_job_execution.save()
    management_job_execution.refresh_from_db()
    assert management_job_execution.status == ExecutionStatus.FAILED
    assert management_job_execution.errors == "Database connection timeout"


@pytest.mark.django_db
def test_execution_status_enum():
    assert ExecutionStatus.PENDING == "pending"
    assert ExecutionStatus.RUNNING == "running"
    assert ExecutionStatus.COMPLETED == "completed"
    assert ExecutionStatus.FAILED == "failed"


# -- Relationship and cascade tests --


@pytest.mark.django_db
def test_cascade_delete_job_deletes_schedules(
    management_job, management_job_schedule
):
    job_id = management_job.pk
    management_job.delete()
    assert (
        ManagementJobSchedule.objects.filter(management_job_id=job_id).count()
        == 0
    )


@pytest.mark.django_db
def test_cascade_delete_job_deletes_executions(
    management_job, management_job_execution
):
    job_id = management_job.pk
    management_job.delete()
    assert (
        ManagementJobExecution.objects.filter(management_job_id=job_id).count()
        == 0
    )


@pytest.mark.django_db
def test_multiple_executions_per_job(management_job, default_organization):
    for i in range(3):
        ManagementJobExecution.objects.create(
            management_job=management_job,
            status=ExecutionStatus.COMPLETED,
            output=f"Run {i}",
            organization=default_organization,
        )
    assert management_job.executions.count() == 3


@pytest.mark.django_db
def test_multiple_schedules_per_job(management_job, default_organization):
    ManagementJobSchedule.objects.create(
        management_job=management_job,
        schedule="0 3 * * *",
        organization=default_organization,
    )
    ManagementJobSchedule.objects.create(
        management_job=management_job,
        schedule="0 6 * * *",
        organization=default_organization,
    )
    assert management_job.schedules.count() == 2
