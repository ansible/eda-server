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

"""Tests for project task monitoring functionality with dispatcherd."""

from unittest.mock import Mock, patch

import pytest

from aap_eda.tasks.project import (
    check_project_queue_health,
    monitor_project_tasks,
)


@pytest.mark.django_db
@patch("aap_eda.tasks.project.advisory_lock")
def test_monitor_project_tasks_acquires_lock(mock_advisory_lock):
    """Test that monitor_project_tasks properly uses advisory locking."""
    mock_lock = Mock()
    mock_lock.__enter__ = Mock(return_value=True)  # Lock acquired
    mock_lock.__exit__ = Mock(return_value=None)
    mock_advisory_lock.return_value = mock_lock

    # Should not raise an exception
    monitor_project_tasks()

    mock_advisory_lock.assert_called_once_with(
        "monitor_project_tasks", wait=False
    )


@pytest.mark.django_db
@patch("aap_eda.tasks.project.advisory_lock")
@patch("aap_eda.tasks.project.logger")
def test_monitor_project_tasks_lock_not_acquired(
    mock_logger, mock_advisory_lock
):
    """Test monitor_project_tasks exits gracefully when lock not acquired."""
    mock_lock = Mock()
    mock_lock.__enter__ = Mock(return_value=False)  # Lock not acquired
    mock_lock.__exit__ = Mock(return_value=None)
    mock_advisory_lock.return_value = mock_lock

    monitor_project_tasks()

    # Should log that another task is running
    mock_logger.debug.assert_called_once_with(
        "Another task already running monitor_project_tasks, exiting"
    )


@pytest.mark.django_db
def test_monitor_project_tasks_scheduled():
    """Test that monitor_project_tasks can be called without errors."""
    # This tests the basic function execution path
    # Note: This test doesn't mock the advisory lock to test the real path
    # If no exception is raised, the function works correctly
    monitor_project_tasks()


@patch("aap_eda.tasks.project.check_rulebook_queue_health")
def test_check_project_queue_health_success(mock_check_rulebook_health):
    """Test check_project_queue_health returns True when queue is healthy."""
    mock_check_rulebook_health.return_value = True

    result = check_project_queue_health()

    assert result is True
    mock_check_rulebook_health.assert_called_once_with("default")


@patch("aap_eda.tasks.project.check_rulebook_queue_health")
def test_check_project_queue_health_failure(mock_check_rulebook_health):
    """Test check_project_queue_health returns False when queue unhealthy."""
    mock_check_rulebook_health.return_value = False

    result = check_project_queue_health()

    assert result is False
    mock_check_rulebook_health.assert_called_once_with("default")


@patch("aap_eda.tasks.project.check_rulebook_queue_health")
def test_check_project_queue_health_exception(mock_check_rulebook_health):
    """Test check_project_queue_health returns False when exception occurs."""
    mock_check_rulebook_health.side_effect = Exception("Connection timeout")

    result = check_project_queue_health()

    assert result is False
    mock_check_rulebook_health.assert_called_once_with("default")


@patch("aap_eda.tasks.project.logger")
@patch("aap_eda.tasks.project.check_rulebook_queue_health")
def test_check_project_queue_health_logs_exceptions(
    mock_check_rulebook_health, mock_logger
):
    """Test check_project_queue_health logs exceptions properly."""
    test_exception = RuntimeError("Dispatcherd connection error")
    mock_check_rulebook_health.side_effect = test_exception

    result = check_project_queue_health()

    assert result is False
    mock_check_rulebook_health.assert_called_once_with("default")

    # Verify error was logged with exception info
    mock_logger.error.assert_called_once()
    log_call = mock_logger.error.call_args
    assert "Project queue health check failed" in log_call[0][0]
    assert log_call[1]["exc_info"] is True


@patch("aap_eda.tasks.project.check_rulebook_queue_health")
def test_check_project_queue_health_connection_error(
    mock_check_rulebook_health,
):
    """Test check_project_queue_health handles connection errors."""
    mock_check_rulebook_health.side_effect = ConnectionError(
        "Failed to connect"
    )

    result = check_project_queue_health()

    assert result is False
    mock_check_rulebook_health.assert_called_once_with("default")


@patch("aap_eda.tasks.project.check_rulebook_queue_health")
def test_check_project_queue_health_timeout_error(mock_check_rulebook_health):
    """Test check_project_queue_health handles timeout errors."""
    mock_check_rulebook_health.side_effect = TimeoutError(
        "Health check timeout"
    )

    result = check_project_queue_health()

    assert result is False
    mock_check_rulebook_health.assert_called_once_with("default")


@patch("aap_eda.tasks.project.utils.sanitize_postgres_identifier")
@patch("aap_eda.tasks.project.check_rulebook_queue_health")
def test_check_project_queue_health_sanitizes_queue_name(
    mock_check_rulebook_health, mock_sanitize
):
    """Test check_project_queue_health sanitizes the queue name."""
    mock_sanitize.return_value = "sanitized_default"
    mock_check_rulebook_health.return_value = True

    result = check_project_queue_health()

    assert result is True
    mock_sanitize.assert_called_once_with("default")
    mock_check_rulebook_health.assert_called_once_with("sanitized_default")
