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

"""Integration tests for dispatcherd functionality in project tasks."""

import uuid
from unittest.mock import patch

import pytest
from django.conf import settings

from aap_eda.core import models
from aap_eda.tasks import project

#################################################################
# Tests for project health check integration
#################################################################


@pytest.mark.django_db
@patch("aap_eda.tasks.project.check_rulebook_queue_health")
def test_check_project_queue_health_success(mock_health_check):
    """Test successful project queue health check."""
    mock_health_check.return_value = True

    result = project.check_project_queue_health()

    assert result is True
    mock_health_check.assert_called_once_with("default")


@pytest.mark.django_db
@patch("aap_eda.tasks.project.check_rulebook_queue_health")
def test_check_project_queue_health_failure(mock_health_check):
    """Test failed project queue health check."""
    mock_health_check.return_value = False

    result = project.check_project_queue_health()

    assert result is False
    mock_health_check.assert_called_once_with("default")


@pytest.mark.django_db
@patch("aap_eda.tasks.project.check_rulebook_queue_health")
@patch("aap_eda.tasks.project.logger")
def test_check_project_queue_health_exception_handling(
    mock_logger, mock_health_check
):
    """Test exception handling in project queue health check."""
    mock_health_check.side_effect = ConnectionError("Connection failed")

    result = project.check_project_queue_health()

    assert result is False
    mock_health_check.assert_called_once_with("default")
    mock_logger.error.assert_called_once()
    # Verify the error message contains expected content
    call_args = mock_logger.error.call_args
    assert "Project queue health check failed" in call_args[0][0]
    assert call_args[1]["exc_info"] is True


@pytest.mark.django_db
@patch("aap_eda.tasks.project.utils.sanitize_postgres_identifier")
@patch("aap_eda.tasks.project.check_rulebook_queue_health")
def test_check_project_queue_health_queue_sanitization(
    mock_health_check, mock_sanitize
):
    """Test that project queue name is sanitized."""
    mock_sanitize.return_value = "sanitized_default"
    mock_health_check.return_value = True

    result = project.check_project_queue_health()

    assert result is True
    mock_sanitize.assert_called_once_with(project.PROJECT_TASKS_QUEUE)
    mock_health_check.assert_called_once_with("sanitized_default")


#################################################################
# Tests for project import task submission
#################################################################


@pytest.mark.django_db
@patch("aap_eda.tasks.project.submit_task")
def test_import_project_calls_submit_task(mock_submit):
    """Test that import_project calls dispatcherd submit_task."""
    test_project_id = 123
    test_uuid = str(uuid.uuid4())
    mock_submit.return_value = ({"uuid": test_uuid}, "default")

    result = project.import_project(test_project_id)

    assert result == test_uuid
    mock_submit.assert_called_once()
    call_args = mock_submit.call_args

    # Verify function and arguments
    assert call_args[0][0] == project._import_project
    assert call_args[1]["args"] == (test_project_id,)
    assert call_args[1]["queue"] == "default"
    assert call_args[1]["timeout"] == settings.DISPATCHERD_PROJECT_TASK_TIMEOUT


@pytest.mark.django_db
@patch("aap_eda.tasks.project.utils.sanitize_postgres_identifier")
@patch("aap_eda.tasks.project.submit_task")
def test_import_project_queue_sanitization(mock_submit, mock_sanitize):
    """Test that import_project sanitizes queue name."""
    test_project_id = 123
    test_uuid = str(uuid.uuid4())
    sanitized_queue = "sanitized_default"

    mock_sanitize.return_value = sanitized_queue
    mock_submit.return_value = ({"uuid": test_uuid}, sanitized_queue)

    result = project.import_project(test_project_id)

    assert result == test_uuid
    mock_sanitize.assert_called_once_with(project.PROJECT_TASKS_QUEUE)
    mock_submit.assert_called_once()

    call_args = mock_submit.call_args
    assert call_args[1]["queue"] == sanitized_queue


@pytest.mark.django_db
@patch("aap_eda.tasks.project.submit_task")
def test_import_project_timeout_configuration(mock_submit):
    """Test that import_project uses correct timeout setting."""
    test_project_id = 456
    test_uuid = str(uuid.uuid4())
    mock_submit.return_value = ({"uuid": test_uuid}, "default")

    project.import_project(test_project_id)

    mock_submit.assert_called_once()
    call_args = mock_submit.call_args
    assert call_args[1]["timeout"] == settings.DISPATCHERD_PROJECT_TASK_TIMEOUT


#################################################################
# Tests for project sync task submission
#################################################################


@pytest.mark.django_db
@patch("aap_eda.tasks.project.submit_task")
def test_sync_project_calls_submit_task(mock_submit):
    """Test that sync_project calls dispatcherd submit_task."""
    test_project_id = 789
    test_uuid = str(uuid.uuid4())
    mock_submit.return_value = ({"uuid": test_uuid}, "default")

    result = project.sync_project(test_project_id)

    assert result == test_uuid
    mock_submit.assert_called_once()
    call_args = mock_submit.call_args

    # Verify function and arguments
    assert call_args[0][0] == project._sync_project
    assert call_args[1]["args"] == (test_project_id,)
    assert call_args[1]["queue"] == "default"
    assert call_args[1]["timeout"] == settings.DISPATCHERD_PROJECT_TASK_TIMEOUT


@pytest.mark.django_db
@patch("aap_eda.tasks.project.utils.sanitize_postgres_identifier")
@patch("aap_eda.tasks.project.submit_task")
def test_sync_project_queue_sanitization(mock_submit, mock_sanitize):
    """Test that sync_project sanitizes queue name."""
    test_project_id = 999
    test_uuid = str(uuid.uuid4())
    sanitized_queue = "sanitized_default"

    mock_sanitize.return_value = sanitized_queue
    mock_submit.return_value = ({"uuid": test_uuid}, sanitized_queue)

    result = project.sync_project(test_project_id)

    assert result == test_uuid
    mock_sanitize.assert_called_once_with(project.PROJECT_TASKS_QUEUE)
    mock_submit.assert_called_once()

    call_args = mock_submit.call_args
    assert call_args[1]["queue"] == sanitized_queue


@pytest.mark.django_db
@patch("aap_eda.tasks.project.submit_task")
def test_sync_project_timeout_configuration(mock_submit):
    """Test that sync_project uses correct timeout setting."""
    test_project_id = 111
    test_uuid = str(uuid.uuid4())
    mock_submit.return_value = ({"uuid": test_uuid}, "default")

    project.sync_project(test_project_id)

    mock_submit.assert_called_once()
    call_args = mock_submit.call_args
    assert call_args[1]["timeout"] == settings.DISPATCHERD_PROJECT_TASK_TIMEOUT


#################################################################
# Tests for project monitoring with advisory locks
#################################################################


@pytest.mark.django_db
@patch("aap_eda.tasks.project.advisory_lock")
def test_monitor_project_tasks_advisory_lock_acquired(mock_advisory_lock):
    """Test monitor_project_tasks when advisory lock is acquired."""
    mock_advisory_lock.return_value.__enter__.return_value = True

    with patch("aap_eda.tasks.project._monitor_project_tasks") as mock_monitor:
        project.monitor_project_tasks()

    mock_advisory_lock.assert_called_once_with(
        "monitor_project_tasks", wait=False
    )
    mock_monitor.assert_called_once()


@pytest.mark.django_db
@patch("aap_eda.tasks.project.advisory_lock")
@patch("aap_eda.tasks.project.logger")
def test_monitor_project_tasks_advisory_lock_not_acquired(
    mock_logger, mock_advisory_lock
):
    """Test monitor_project_tasks when advisory lock is not acquired."""
    mock_advisory_lock.return_value.__enter__.return_value = False

    with patch("aap_eda.tasks.project._monitor_project_tasks") as mock_monitor:
        project.monitor_project_tasks()

    mock_advisory_lock.assert_called_once_with(
        "monitor_project_tasks", wait=False
    )
    mock_monitor.assert_not_called()
    mock_logger.debug.assert_called_once_with(
        "Another task already running monitor_project_tasks, exiting"
    )


#################################################################
# Tests for internal project task functions
#################################################################


@pytest.mark.django_db
@patch("aap_eda.tasks.project.advisory_lock")
def test_import_project_internal_advisory_lock_acquired(
    mock_advisory_lock, default_organization
):
    """Test _import_project when advisory lock is acquired."""
    test_project = models.Project.objects.create(
        name="test-project",
        url="https://github.com/test/test.git",
        organization=default_organization,
    )

    mock_advisory_lock.return_value.__enter__.return_value = True

    with patch("aap_eda.tasks.project._import_project_no_lock") as mock_import:
        project._import_project(test_project.id)

    mock_advisory_lock.assert_called_once_with(
        f"import_project_{test_project.id}", wait=False
    )
    mock_import.assert_called_once_with(test_project.id)


@pytest.mark.django_db
@patch("aap_eda.tasks.project.advisory_lock")
@patch("aap_eda.tasks.project.logger")
def test_import_project_internal_advisory_lock_not_acquired(
    mock_logger, mock_advisory_lock, default_organization
):
    """Test _import_project when advisory lock is not acquired."""
    test_project = models.Project.objects.create(
        name="test-project",
        url="https://github.com/test/test.git",
        organization=default_organization,
    )

    mock_advisory_lock.return_value.__enter__.return_value = False

    with patch("aap_eda.tasks.project._import_project_no_lock") as mock_import:
        project._import_project(test_project.id)

    mock_advisory_lock.assert_called_once_with(
        f"import_project_{test_project.id}", wait=False
    )
    mock_import.assert_not_called()
    mock_logger.debug.assert_called_once()

    # Verify log message content
    call_args = mock_logger.debug.call_args[0][0]
    assert (
        f"Another task already importing project {test_project.id}"
        in call_args
    )


@pytest.mark.django_db
@patch("aap_eda.tasks.project.advisory_lock")
def test_sync_project_internal_advisory_lock_acquired(
    mock_advisory_lock, default_organization
):
    """Test _sync_project when advisory lock is acquired."""
    test_project = models.Project.objects.create(
        name="test-project",
        url="https://github.com/test/test.git",
        organization=default_organization,
    )

    mock_advisory_lock.return_value.__enter__.return_value = True

    with patch("aap_eda.tasks.project._sync_project_no_lock") as mock_sync:
        project._sync_project(test_project.id)

    mock_advisory_lock.assert_called_once_with(
        f"sync_project_{test_project.id}", wait=False
    )
    mock_sync.assert_called_once_with(test_project.id)


@pytest.mark.django_db
@patch("aap_eda.tasks.project.advisory_lock")
@patch("aap_eda.tasks.project.logger")
def test_sync_project_internal_advisory_lock_not_acquired(
    mock_logger, mock_advisory_lock, default_organization
):
    """Test _sync_project when advisory lock is not acquired."""
    test_project = models.Project.objects.create(
        name="test-project",
        url="https://github.com/test/test.git",
        organization=default_organization,
    )

    mock_advisory_lock.return_value.__enter__.return_value = False

    with patch("aap_eda.tasks.project._sync_project_no_lock") as mock_sync:
        project._sync_project(test_project.id)

    mock_advisory_lock.assert_called_once_with(
        f"sync_project_{test_project.id}", wait=False
    )
    mock_sync.assert_not_called()
    mock_logger.debug.assert_called_once()

    # Verify log message content
    call_args = mock_logger.debug.call_args[0][0]
    assert (
        f"Another task already syncing project {test_project.id}" in call_args
    )


#################################################################
# Tests for project monitoring implementation
#################################################################


@pytest.mark.django_db
@patch("aap_eda.tasks.project.logger")
def test_monitor_project_tasks_internal_no_unfinished_projects(mock_logger):
    """Test _monitor_project_tasks with no unfinished projects."""
    # No projects exist, so no unfinished ones
    project._monitor_project_tasks()

    # Should log start and complete
    assert mock_logger.info.call_count == 2
    start_call = mock_logger.info.call_args_list[0][0][0]
    complete_call = mock_logger.info.call_args_list[1][0][0]

    assert "Task started: Monitor project tasks" in start_call
    assert "Task complete: Monitor project tasks" in complete_call


@pytest.mark.django_db
@patch("aap_eda.tasks.project.logger")
def test_monitor_project_tasks_internal_with_unfinished_projects(
    mock_logger, default_organization
):
    """Test _monitor_project_tasks with unfinished projects."""
    # Create projects in transition states
    models.Project.objects.create(
        name="pending-project",
        url="https://github.com/test/pending.git",
        organization=default_organization,
        import_state=models.Project.ImportState.PENDING,
    )
    models.Project.objects.create(
        name="running-project",
        url="https://github.com/test/running.git",
        organization=default_organization,
        import_state=models.Project.ImportState.RUNNING,
    )
    models.Project.objects.create(
        name="completed-project",
        url="https://github.com/test/completed.git",
        organization=default_organization,
        import_state=models.Project.ImportState.COMPLETED,
    )

    project._monitor_project_tasks()

    # Should log start, unfinished count, and complete
    assert mock_logger.info.call_count == 3

    start_call = mock_logger.info.call_args_list[0][0][0]
    unfinished_call = mock_logger.info.call_args_list[1][0][0]
    complete_call = mock_logger.info.call_args_list[2][0][0]

    assert "Task started: Monitor project tasks" in start_call
    assert "Found 2 projects in transition states" in unfinished_call
    assert "Dispatcherd handles task recovery" in unfinished_call
    assert "Task complete: Monitor project tasks" in complete_call
