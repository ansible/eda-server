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

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError
from django.utils import timezone

from aap_eda.core import models
from aap_eda.services.project import ProjectImportError
from aap_eda.tasks.project import (
    _get_project_safely,
    _handle_project_error_recovery,
    _import_project_no_lock,
    _monitor_project_tasks,
    _sync_project_no_lock,
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


# Tests for new critical exception handling functions (AAP-64076)


@pytest.mark.django_db
def test_get_project_safely_success(default_organization):
    """Test _get_project_safely returns project when it exists."""
    project = models.Project.objects.create(
        name="Test Project",
        url="https://github.com/example/repo",
        organization=default_organization,
    )

    result = _get_project_safely(project.id)

    assert result is not None
    assert result.id == project.id
    assert result.name == "Test Project"


@pytest.mark.django_db
def test_get_project_safely_does_not_exist():
    """Test _get_project_safely returns None for non-existent project."""
    non_existent_id = 99999

    result = _get_project_safely(non_existent_id)

    assert result is None


@pytest.mark.django_db
@patch("aap_eda.tasks.project.models.Project.objects.get")
def test_get_project_safely_database_error_propagates(mock_get):
    """Test _get_project_safely lets DatabaseError propagate to callers."""
    mock_get.side_effect = DatabaseError("Connection lost")

    with pytest.raises(DatabaseError):
        _get_project_safely(123)


@pytest.mark.django_db
@patch("aap_eda.tasks.project.models.Project.objects.get")
def test_get_project_safely_generic_exception_propagates(mock_get):
    """Test _get_project_safely lets generic exceptions propagate."""
    mock_get.side_effect = RuntimeError("Unexpected error")

    with pytest.raises(RuntimeError):
        _get_project_safely(123)


@pytest.mark.django_db
def test_handle_project_error_recovery_success(default_organization):
    """Test _handle_project_error_recovery resets project state."""
    project = models.Project.objects.create(
        name="Test Project",
        url="https://github.com/example/repo",
        organization=default_organization,
        import_state=models.Project.ImportState.RUNNING,
    )

    _handle_project_error_recovery(project.id, "Test error message")

    project.refresh_from_db()
    assert project.import_state == models.Project.ImportState.FAILED
    assert project.import_error == "Test error message"


@pytest.mark.django_db
@patch("aap_eda.tasks.project.logger")
def test_handle_project_error_recovery_project_deleted(
    mock_logger, default_organization
):
    """Test _handle_project_error_recovery handles deleted projects."""
    project = models.Project.objects.create(
        name="Test Project",
        url="https://github.com/example/repo",
        organization=default_organization,
        import_state=models.Project.ImportState.RUNNING,
    )

    project_id = project.id
    project.delete()

    _handle_project_error_recovery(project_id, "Test error")

    # Should log a warning about deleted project
    mock_logger.warning.assert_called_once()
    log_call = mock_logger.warning.call_args
    assert "was deleted during error recovery" in log_call[0][0]


@pytest.mark.django_db
def test_handle_project_error_recovery_completed_project(
    default_organization,
):
    """Test _handle_project_error_recovery skips completed projects."""
    project = models.Project.objects.create(
        name="Test Project",
        url="https://github.com/example/repo",
        organization=default_organization,
        import_state=models.Project.ImportState.COMPLETED,
        import_error="",
    )

    _handle_project_error_recovery(project.id, "Test error message")

    project.refresh_from_db()
    # Should not change completed project
    assert project.import_state == models.Project.ImportState.COMPLETED
    assert project.import_error == ""


@pytest.mark.django_db
@patch("aap_eda.tasks.project._get_project_safely")
@patch("aap_eda.tasks.project.ProjectImportService")
@patch("aap_eda.tasks.project.logger")
def test_import_project_no_lock_success(
    mock_logger, mock_service, mock_get_project, default_organization
):
    """Test _import_project_no_lock handles successful import."""
    project = models.Project.objects.create(
        name="Test Project",
        url="https://github.com/example/repo",
        organization=default_organization,
    )
    mock_get_project.return_value = project
    mock_import_service = Mock()
    mock_service.return_value = mock_import_service

    _import_project_no_lock(project.id)

    mock_get_project.assert_called_once_with(project.id)
    mock_import_service.import_project.assert_called_once_with(project)
    project.refresh_from_db()
    assert project.last_synced_at is not None


@pytest.mark.django_db
@patch("aap_eda.tasks.project._get_project_safely")
@patch("aap_eda.tasks.project.logger")
def test_import_project_no_lock_project_not_found(
    mock_logger, mock_get_project
):
    """Test _import_project_no_lock handles missing project gracefully."""
    mock_get_project.return_value = None

    _import_project_no_lock(999)

    mock_get_project.assert_called_once_with(999)
    # Should log task started and completed with project not found message
    assert mock_logger.info.call_count == 2
    start_call = mock_logger.info.call_args_list[0]
    complete_call = mock_logger.info.call_args_list[1]
    assert "Task started: Import project" in start_call[0][0]
    assert "project not found" in complete_call[0][0]


@pytest.mark.django_db
@patch("aap_eda.tasks.project._get_project_safely")
@patch("aap_eda.tasks.project.ProjectImportService")
@patch("aap_eda.tasks.project._handle_project_error_recovery")
@patch("aap_eda.tasks.project.logger")
def test_import_project_no_lock_project_import_error(
    mock_logger,
    mock_recovery,
    mock_service,
    mock_get_project,
    default_organization,
):
    """Test _import_project_no_lock handles ProjectImportError."""
    project = models.Project.objects.create(
        name="Test Project",
        url="https://github.com/example/repo",
        organization=default_organization,
    )
    mock_get_project.return_value = project
    mock_import_service = Mock()
    mock_import_service.import_project.side_effect = ProjectImportError(
        "Import failed"
    )
    mock_service.return_value = mock_import_service

    _import_project_no_lock(project.id)

    mock_import_service.import_project.assert_called_once_with(project)
    mock_logger.error.assert_called_once()
    log_call = mock_logger.error.call_args
    assert "Project import error for project" in log_call[0][0]
    # Should call error recovery to set FAILED state
    # (transaction.atomic rollback undoes the wrapper's state save)
    mock_recovery.assert_called_once_with(
        project.id, "Import failed: Import failed"
    )


@pytest.mark.django_db
@patch("aap_eda.tasks.project._get_project_safely")
@patch("aap_eda.tasks.project.ProjectImportService")
@patch("aap_eda.tasks.project._handle_project_error_recovery")
@patch("aap_eda.tasks.project.logger")
def test_import_project_no_lock_database_error(
    mock_logger,
    mock_recovery,
    mock_service,
    mock_get_project,
    default_organization,
):
    """Test _import_project_no_lock handles database errors."""
    project = models.Project.objects.create(
        name="Test Project",
        url="https://github.com/example/repo",
        organization=default_organization,
    )
    mock_get_project.return_value = project
    mock_import_service = Mock()
    mock_import_service.import_project.side_effect = DatabaseError("DB error")
    mock_service.return_value = mock_import_service

    _import_project_no_lock(project.id)

    mock_recovery.assert_called_once_with(
        project.id, "Database error during import"
    )
    mock_logger.error.assert_called_once()
    log_call = mock_logger.error.call_args
    assert "Database error during project import" in log_call[0][0]
    assert log_call[1]["exc_info"] is True


@pytest.mark.django_db
@patch("aap_eda.tasks.project._get_project_safely")
@patch("aap_eda.tasks.project.ProjectImportService")
@patch("aap_eda.tasks.project.logger")
def test_sync_project_no_lock_success(
    mock_logger, mock_service, mock_get_project, default_organization
):
    """Test _sync_project_no_lock handles successful sync."""
    project = models.Project.objects.create(
        name="Test Project",
        url="https://github.com/example/repo",
        organization=default_organization,
    )
    mock_get_project.return_value = project
    mock_sync_service = Mock()
    mock_service.return_value = mock_sync_service

    _sync_project_no_lock(project.id)

    mock_get_project.assert_called_once_with(project.id)
    mock_sync_service.sync_project.assert_called_once_with(project)
    project.refresh_from_db()
    assert project.last_synced_at is not None


@pytest.mark.django_db
@patch("aap_eda.tasks.project.settings")
def test_monitor_project_tasks_recovers_stuck_projects(
    mock_settings, default_organization
):
    """Test _monitor_project_tasks recovers stuck RUNNING projects."""
    mock_settings.DISPATCHERD_PROJECT_TASK_TIMEOUT = 300

    # Create a project stuck in RUNNING state for too long
    old_time = timezone.now() - timedelta(seconds=700)  # Beyond 2x timeout
    project = models.Project.objects.create(
        name="Stuck Project",
        url="https://github.com/example/repo",
        organization=default_organization,
        import_state=models.Project.ImportState.RUNNING,
    )
    # Manually set modified_at to simulate old timestamp
    models.Project.objects.filter(id=project.id).update(modified_at=old_time)

    _monitor_project_tasks()

    project.refresh_from_db()
    assert project.import_state == models.Project.ImportState.FAILED
    assert "Task appears to have been abandoned" in project.import_error


@pytest.mark.django_db
@patch("aap_eda.tasks.project.settings")
def test_monitor_project_tasks_recovers_stuck_pending(
    mock_settings, default_organization
):
    """Test _monitor_project_tasks recovers stuck PENDING projects."""
    mock_settings.DISPATCHERD_PROJECT_TASK_TIMEOUT = 300

    # Create a project stuck in PENDING state for too long
    old_time = timezone.now() - timedelta(seconds=700)
    project = models.Project.objects.create(
        name="Stuck Pending Project",
        url="https://github.com/example/repo",
        organization=default_organization,
        import_state=models.Project.ImportState.PENDING,
    )
    models.Project.objects.filter(id=project.id).update(modified_at=old_time)

    _monitor_project_tasks()

    project.refresh_from_db()
    assert project.import_state == models.Project.ImportState.FAILED
    assert "Task was stuck in pending state" in project.import_error


@pytest.mark.django_db
@patch("aap_eda.tasks.project.settings")
def test_monitor_project_tasks_ignores_recent_projects(
    mock_settings, default_organization
):
    """Test _monitor_project_tasks ignores recently modified projects."""
    mock_settings.DISPATCHERD_PROJECT_TASK_TIMEOUT = 300

    project = models.Project.objects.create(
        name="Recent Project",
        url="https://github.com/example/repo",
        organization=default_organization,
        import_state=models.Project.ImportState.RUNNING,
    )

    _monitor_project_tasks()

    project.refresh_from_db()
    # Should still be running as it's recent
    assert project.import_state == models.Project.ImportState.RUNNING


@pytest.mark.django_db
@patch("aap_eda.tasks.project.settings")
@patch("aap_eda.tasks.project.logger")
def test_monitor_project_tasks_handles_concurrent_access(
    mock_logger, mock_settings, default_organization
):
    """Test _monitor_project_tasks handles race conditions gracefully."""
    mock_settings.DISPATCHERD_PROJECT_TASK_TIMEOUT = 300

    # Create a project that will be deleted during monitoring
    old_time = timezone.now() - timedelta(seconds=700)
    project = models.Project.objects.create(
        name="Soon to be deleted",
        url="https://github.com/example/repo",
        organization=default_organization,
        import_state=models.Project.ImportState.RUNNING,
    )
    models.Project.objects.filter(id=project.id).update(modified_at=old_time)

    # Mock the project to be already completed by the time we try to recover it
    with patch(
        "aap_eda.tasks.project.models.Project.objects.select_for_update"
    ) as mock_select:
        mock_queryset = Mock()
        mock_select.return_value = mock_queryset
        fresh_project = Mock()
        fresh_project.import_state = models.Project.ImportState.COMPLETED
        mock_queryset.get.return_value = fresh_project

        _monitor_project_tasks()

        # Should not save the project if it's already completed
        fresh_project.save.assert_not_called()


# ------------------------------------------------------------------
# Additional coverage: _import_project_no_lock generic Exception
# ------------------------------------------------------------------


@pytest.mark.django_db
@patch("aap_eda.tasks.project._get_project_safely")
@patch("aap_eda.tasks.project.ProjectImportService")
@patch("aap_eda.tasks.project._handle_project_error_recovery")
@patch("aap_eda.tasks.project.logger")
def test_import_project_no_lock_unexpected_exception(
    mock_logger,
    mock_recovery,
    mock_service,
    mock_get_project,
    default_organization,
):
    """Test _import_project_no_lock handles unexpected exceptions."""
    project = models.Project.objects.create(
        name="Test Project",
        url="https://github.com/example/repo",
        organization=default_organization,
    )
    mock_get_project.return_value = project
    mock_import_service = Mock()
    mock_import_service.import_project.side_effect = RuntimeError(
        "Something broke"
    )
    mock_service.return_value = mock_import_service

    _import_project_no_lock(project.id)

    mock_recovery.assert_called_once_with(
        project.id,
        "Unexpected error during import: Something broke",
    )
    mock_logger.error.assert_called_once()
    log_call = mock_logger.error.call_args
    assert "Unexpected error during project import" in log_call[0][0]
    assert log_call[1]["exc_info"] is True


# ------------------------------------------------------------------
# Additional coverage: _sync_project_no_lock all error paths
# ------------------------------------------------------------------


@pytest.mark.django_db
@patch("aap_eda.tasks.project._get_project_safely")
@patch("aap_eda.tasks.project.logger")
def test_sync_project_no_lock_project_not_found(mock_logger, mock_get_project):
    """Test _sync_project_no_lock handles missing project."""
    mock_get_project.return_value = None

    _sync_project_no_lock(999)

    mock_get_project.assert_called_once_with(999)
    assert mock_logger.info.call_count == 2
    complete_call = mock_logger.info.call_args_list[1]
    assert "project not found" in complete_call[0][0]


@pytest.mark.django_db
@patch("aap_eda.tasks.project._get_project_safely")
@patch("aap_eda.tasks.project.ProjectImportService")
@patch("aap_eda.tasks.project._handle_project_error_recovery")
@patch("aap_eda.tasks.project.logger")
def test_sync_project_no_lock_project_import_error(
    mock_logger,
    mock_recovery,
    mock_service,
    mock_get_project,
    default_organization,
):
    """Test _sync_project_no_lock handles ProjectImportError."""
    project = models.Project.objects.create(
        name="Test Project",
        url="https://github.com/example/repo",
        organization=default_organization,
    )
    mock_get_project.return_value = project
    mock_sync_service = Mock()
    mock_sync_service.sync_project.side_effect = ProjectImportError(
        "Sync failed"
    )
    mock_service.return_value = mock_sync_service

    _sync_project_no_lock(project.id)

    mock_logger.error.assert_called_once()
    log_call = mock_logger.error.call_args
    assert "Project sync error for project" in log_call[0][0]
    mock_recovery.assert_called_once_with(
        project.id, "Sync failed: Sync failed"
    )


@pytest.mark.django_db
@patch("aap_eda.tasks.project._get_project_safely")
@patch("aap_eda.tasks.project.ProjectImportService")
@patch("aap_eda.tasks.project._handle_project_error_recovery")
@patch("aap_eda.tasks.project.logger")
def test_sync_project_no_lock_database_error(
    mock_logger,
    mock_recovery,
    mock_service,
    mock_get_project,
    default_organization,
):
    """Test _sync_project_no_lock handles database errors."""
    project = models.Project.objects.create(
        name="Test Project",
        url="https://github.com/example/repo",
        organization=default_organization,
    )
    mock_get_project.return_value = project
    mock_sync_service = Mock()
    mock_sync_service.sync_project.side_effect = DatabaseError("DB error")
    mock_service.return_value = mock_sync_service

    _sync_project_no_lock(project.id)

    mock_recovery.assert_called_once_with(
        project.id, "Database error during sync"
    )
    mock_logger.error.assert_called_once()
    assert mock_logger.error.call_args[1]["exc_info"] is True


@pytest.mark.django_db
@patch("aap_eda.tasks.project._get_project_safely")
@patch("aap_eda.tasks.project.ProjectImportService")
@patch("aap_eda.tasks.project._handle_project_error_recovery")
@patch("aap_eda.tasks.project.logger")
def test_sync_project_no_lock_unexpected_exception(
    mock_logger,
    mock_recovery,
    mock_service,
    mock_get_project,
    default_organization,
):
    """Test _sync_project_no_lock handles unexpected exceptions."""
    project = models.Project.objects.create(
        name="Test Project",
        url="https://github.com/example/repo",
        organization=default_organization,
    )
    mock_get_project.return_value = project
    mock_sync_service = Mock()
    mock_sync_service.sync_project.side_effect = RuntimeError(
        "Something broke"
    )
    mock_service.return_value = mock_sync_service

    _sync_project_no_lock(project.id)

    mock_recovery.assert_called_once_with(
        project.id,
        "Unexpected error during sync: Something broke",
    )
    mock_logger.error.assert_called_once()
    assert mock_logger.error.call_args[1]["exc_info"] is True


# ------------------------------------------------------------------
# Additional coverage: _recover_stuck_projects error paths
# ------------------------------------------------------------------


@pytest.mark.django_db
@patch("aap_eda.tasks.project.settings")
@patch("aap_eda.tasks.project.logger")
def test_recover_stuck_projects_deleted_during_recovery(
    mock_logger, mock_settings, default_organization
):
    """Test _recover_stuck_projects handles project deleted mid-recovery."""
    mock_settings.DISPATCHERD_PROJECT_TASK_TIMEOUT = 300

    old_time = timezone.now() - timedelta(seconds=700)
    project = models.Project.objects.create(
        name="Will be deleted",
        url="https://github.com/example/repo",
        organization=default_organization,
        import_state=models.Project.ImportState.RUNNING,
    )
    models.Project.objects.filter(id=project.id).update(modified_at=old_time)

    # Simulate deletion between queryset iteration and select_for_update
    with patch(
        "aap_eda.tasks.project.models.Project.objects" ".select_for_update"
    ) as mock_select:
        mock_qs = Mock()
        mock_select.return_value = mock_qs
        mock_qs.get.side_effect = ObjectDoesNotExist("Project not found")

        _monitor_project_tasks()

    warning_calls = [c[0][0] for c in mock_logger.warning.call_args_list]
    assert any("was deleted" in msg for msg in warning_calls)


@pytest.mark.django_db
@patch("aap_eda.tasks.project.settings")
@patch("aap_eda.tasks.project.logger")
def test_recover_stuck_projects_database_error(
    mock_logger, mock_settings, default_organization
):
    """Test _recover_stuck_projects handles DatabaseError during recovery."""
    mock_settings.DISPATCHERD_PROJECT_TASK_TIMEOUT = 300

    old_time = timezone.now() - timedelta(seconds=700)
    project = models.Project.objects.create(
        name="DB Error Project",
        url="https://github.com/example/repo",
        organization=default_organization,
        import_state=models.Project.ImportState.RUNNING,
    )
    models.Project.objects.filter(id=project.id).update(modified_at=old_time)

    with patch(
        "aap_eda.tasks.project.models.Project.objects" ".select_for_update"
    ) as mock_select:
        mock_qs = Mock()
        mock_select.return_value = mock_qs
        mock_qs.get.side_effect = DatabaseError("Connection lost")

        _monitor_project_tasks()

    error_calls = [c[0][0] for c in mock_logger.error.call_args_list]
    assert any("Failed to recover project" in msg for msg in error_calls)


# ------------------------------------------------------------------
# Additional coverage: _handle_project_error_recovery
# ------------------------------------------------------------------


@pytest.mark.django_db
def test_handle_project_error_recovery_pending_state(
    default_organization,
):
    """Test _handle_project_error_recovery resets PENDING projects."""
    project = models.Project.objects.create(
        name="Test Project",
        url="https://github.com/example/repo",
        organization=default_organization,
        import_state=models.Project.ImportState.PENDING,
    )

    _handle_project_error_recovery(project.id, "Error in pending state")

    project.refresh_from_db()
    assert project.import_state == models.Project.ImportState.FAILED
    assert project.import_error == "Error in pending state"


@pytest.mark.django_db
@patch("aap_eda.tasks.project.logger")
def test_handle_project_error_recovery_database_error(
    mock_logger, default_organization
):
    """Test _handle_project_error_recovery handles DatabaseError."""
    project = models.Project.objects.create(
        name="Test Project",
        url="https://github.com/example/repo",
        organization=default_organization,
        import_state=models.Project.ImportState.RUNNING,
    )

    with patch(
        "aap_eda.tasks.project.models.Project.objects" ".select_for_update"
    ) as mock_select:
        mock_qs = Mock()
        mock_select.return_value = mock_qs
        mock_qs.get.side_effect = DatabaseError("Connection lost")

        _handle_project_error_recovery(project.id, "Test error")

    # Should log at CRITICAL level
    mock_logger.critical.assert_called_once()
    log_call = mock_logger.critical.call_args
    assert "Failed to reset project" in log_call[0][0]
    assert "project may be stuck" in log_call[0][0]
    assert log_call[1]["exc_info"] is True
