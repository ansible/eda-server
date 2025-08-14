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

import uuid
from unittest import mock

import pytest

from aap_eda.core import models
from aap_eda.core.tasking import DefaultWorker, Queue
from aap_eda.tasks.project import monitor_project_tasks


def fake_job():
    pass


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.project.import_project")
def test_monitor_project_tasks_import(
    import_task_mock: mock.Mock,
    default_organization: models.Organization,
    default_queue: Queue,
):
    """Test monitor_project_tasks rq task.

    Test that monitor_project_tasks recreate the task
    when import project task is stuck.
    """
    job_id = str(uuid.uuid4())
    import_task_mock.return_value = job_id

    project = models.Project.objects.create(
        name="test_monitor_project_tasks",
        url="https://git.example.com/acme/project-01",
        import_state=models.Project.ImportState.PENDING,
        organization=default_organization,
    )
    default_queue.enqueue(monitor_project_tasks, default_queue.name)

    worker = DefaultWorker(
        [default_queue], connection=default_queue.connection
    )
    worker.work(burst=True)
    project.refresh_from_db()
    assert str(project.import_task_id) == job_id


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.project.sync_project")
def test_monitor_project_tasks_sync(
    sync_task_mock: mock.Mock,
    default_organization: models.Organization,
    default_queue: Queue,
):
    """Test monitor_project_tasks rq task.

    Test that monitor_project_tasks recreate the task
    when sync project task is stuck.
    """
    job_id = str(uuid.uuid4())
    sync_task_mock.return_value = job_id

    project = models.Project.objects.create(
        name="test_monitor_project_tasks",
        url="https://git.example.com/acme/project-01",
        import_state=models.Project.ImportState.PENDING,
        git_hash="dummy-hash",
        organization=default_organization,
    )
    default_queue.enqueue(monitor_project_tasks, default_queue.name)

    worker = DefaultWorker(
        [default_queue], connection=default_queue.connection
    )
    worker.work(burst=True)
    project.refresh_from_db()
    assert str(project.import_task_id) == job_id


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.project.sync_project")
def test_monitor_project_tasks_with_job(
    sync_task_mock: mock.Mock,
    default_organization: models.Organization,
    default_queue: Queue,
):
    """Test monitor_project_tasks rq task.

    Test that monitor_project_tasks does not recreate the task
    when sync project task is not stuck
    """
    job_id = str(uuid.uuid4())
    sync_task_mock.return_value = job_id
    expected_job_id = str(uuid.uuid4())

    project = models.Project.objects.create(
        name="test_monitor_project_tasks",
        url="https://git.example.com/acme/project-01",
        import_state=models.Project.ImportState.PENDING,
        git_hash="dummy-hash",
        import_task_id=expected_job_id,
        organization=default_organization,
    )
    default_queue.enqueue(fake_job, job_id=expected_job_id)
    default_queue.enqueue(monitor_project_tasks, default_queue.name)

    worker = DefaultWorker(
        [default_queue], connection=default_queue.connection
    )
    worker.work(burst=True)
    project.refresh_from_db()
    assert str(project.import_task_id) == expected_job_id


@pytest.mark.django_db
def test_monitor_project_tasks_running_state_missing_job(
    default_organization: models.Organization,
    default_queue: Queue,
):
    """Test monitor_project_tasks handles RUNNING projects with missing jobs.

    Test that projects in RUNNING state without corresponding jobs
    are marked as FAILED with appropriate error message.
    """
    project = models.Project.objects.create(
        name="test_running_missing_job",
        url="https://git.example.com/acme/project-running",
        import_state=models.Project.ImportState.RUNNING,
        import_task_id=uuid.uuid4(),
        organization=default_organization,
    )

    default_queue.enqueue(monitor_project_tasks, default_queue.name)

    worker = DefaultWorker(
        [default_queue], connection=default_queue.connection
    )
    worker.work(burst=True)

    project.refresh_from_db()
    assert project.import_state == models.Project.ImportState.FAILED
    assert project.import_task_id is None
    assert (
        project.import_error
        == "Project was in running state but is no longer running"
    )


@pytest.mark.django_db
def test_monitor_project_tasks_ignores_completed_and_failed_projects(
    default_organization: models.Organization,
    default_queue: Queue,
):
    """Test monitor_project_tasks ignores projects in COMPLETED and FAILED
    states.

    Test that projects in terminal states (COMPLETED, FAILED) are not
    processed even if they have missing jobs.
    """
    # Create projects in terminal states
    completed_project = models.Project.objects.create(
        name="test_completed",
        url="https://git.example.com/acme/project-completed",
        import_state=models.Project.ImportState.COMPLETED,
        import_task_id=uuid.uuid4(),
        organization=default_organization,
    )

    failed_project = models.Project.objects.create(
        name="test_failed",
        url="https://git.example.com/acme/project-failed",
        import_state=models.Project.ImportState.FAILED,
        import_task_id=uuid.uuid4(),
        organization=default_organization,
    )

    default_queue.enqueue(monitor_project_tasks, default_queue.name)

    worker = DefaultWorker(
        [default_queue], connection=default_queue.connection
    )
    worker.work(burst=True)

    # Refresh and verify states haven't changed
    completed_project.refresh_from_db()
    failed_project.refresh_from_db()

    assert (
        completed_project.import_state == models.Project.ImportState.COMPLETED
    )
    assert failed_project.import_state == models.Project.ImportState.FAILED


def failing_job():
    """A job that always fails."""
    raise Exception("This job always fails")


@pytest.mark.django_db
def test_monitor_project_tasks_running_state_failed_job(
    default_organization: models.Organization,
    default_queue: Queue,
):
    """Test monitor_project_tasks handles running projects with failed jobs.

    Test that projects in RUNNING state with failed jobs are marked as FAILED.
    """
    # Create a running project
    project = models.Project.objects.create(
        name="test_running_failed_job",
        url="https://git.example.com/acme/running-failed-job",
        import_state=models.Project.ImportState.RUNNING,
        import_task_id=uuid.uuid4(),
        organization=default_organization,
    )

    # Create a job that will actually fail when executed
    failed_job_id = str(project.import_task_id)
    default_queue.enqueue(failing_job, job_id=failed_job_id)

    # Run the failing job first
    worker = DefaultWorker(
        [default_queue], connection=default_queue.connection
    )
    worker.work(burst=True)

    # Now enqueue monitor_project_tasks to check the failed job
    default_queue.enqueue(monitor_project_tasks, default_queue.name)
    worker.work(burst=True)

    # Verify project was marked as failed
    project.refresh_from_db()
    assert project.import_task_id is None
    assert project.import_state == models.Project.ImportState.FAILED
    assert (
        project.import_error
        == "Project was in running state but is no longer running"
    )


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.project.sync_project")
@mock.patch("aap_eda.tasks.project.import_project")
@mock.patch("aap_eda.tasks.project.logger")
def test_monitor_project_tasks_logging(
    logger_mock: mock.Mock,
    import_mock: mock.Mock,
    sync_mock: mock.Mock,
    default_organization: models.Organization,
    default_queue: Queue,
):
    """Test monitor_project_tasks produces expected log messages.

    Test that appropriate log messages are generated for different scenarios.
    """
    import_job_id = str(uuid.uuid4())
    sync_job_id = str(uuid.uuid4())
    import_mock.return_value = import_job_id
    sync_mock.return_value = sync_job_id

    # Create projects for different scenarios
    # Pending project without git_hash - should call import_project
    pending_import_project = models.Project.objects.create(
        name="pending_import_logs",
        url="https://git.example.com/acme/pending-import-logs",
        import_state=models.Project.ImportState.PENDING,
        import_task_id=uuid.uuid4(),
        git_hash="",
        organization=default_organization,
    )

    # Pending project with git_hash - should call sync_project
    pending_sync_project = models.Project.objects.create(
        name="pending_sync_logs",
        url="https://git.example.com/acme/pending-sync-logs",
        import_state=models.Project.ImportState.PENDING,
        import_task_id=uuid.uuid4(),
        git_hash="abc123def456",
        organization=default_organization,
    )

    # Running project - should be marked as failed
    running_project = models.Project.objects.create(
        name="running_for_logs",
        url="https://git.example.com/acme/running-logs",
        import_state=models.Project.ImportState.RUNNING,
        import_task_id=uuid.uuid4(),
        organization=default_organization,
    )

    # Call the internal function directly to ensure mocking works
    from aap_eda.tasks.project import _monitor_project_tasks

    _monitor_project_tasks(default_queue.name)

    # Verify projects were processed
    pending_import_project.refresh_from_db()
    pending_sync_project.refresh_from_db()
    running_project.refresh_from_db()

    # Pending import project should get new import task ID
    assert str(pending_import_project.import_task_id) == import_job_id
    assert (
        pending_import_project.import_state
        == models.Project.ImportState.PENDING
    )

    # Pending sync project should get new sync task ID
    assert str(pending_sync_project.import_task_id) == sync_job_id
    assert (
        pending_sync_project.import_state == models.Project.ImportState.PENDING
    )

    # Running project should be marked as failed
    assert running_project.import_task_id is None
    assert running_project.import_state == models.Project.ImportState.FAILED
    assert (
        running_project.import_error
        == "Project was in running state but is no longer running"
    )

    # Verify expected log messages were produced
    expected_calls = [
        mock.call("Task started: Monitor project tasks"),
        mock.call(
            f"monitor_project_tasks: Project {pending_import_project.name} is "
            "missing a job in the queue. Adding it back."
        ),
        mock.call(
            f"monitor_project_tasks: Project {pending_sync_project.name} is "
            "missing a job in the queue. Adding it back."
        ),
        mock.call(
            f"monitor_project_tasks: Project {running_project.name} was in "
            "running state but is no longer running. Marking as failed."
        ),
        mock.call("Task complete: Monitor project tasks"),
    ]

    # Assert that all expected log calls were made
    logger_mock.info.assert_has_calls(expected_calls, any_order=False)
