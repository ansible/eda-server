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

from aap_eda.tasks.project import monitor_project_tasks


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
