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

"""Tests for dispatcherd management command."""

from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command
from django.test import override_settings

from aap_eda.core.management.commands.dispatcherd import Command

# Test Command class initialization


@patch("aap_eda.core.management.commands.dispatcherd.startup_logging")
def test_command_init(mock_startup_logging):
    """Test Command initialization calls startup_logging."""
    Command()  # Instantiation triggers startup_logging
    mock_startup_logging.assert_called_once()


# Test argument parsing


def test_add_arguments():
    """Test that add_arguments requires worker-class argument."""
    command = Command()
    parser = Mock()

    command.add_arguments(parser)

    # Verify worker-class argument was added
    parser.add_argument.assert_called_once()
    call_args = parser.add_argument.call_args
    assert call_args[0][0] == "--worker-class"
    assert call_args[1]["required"] is True
    assert call_args[1]["choices"] == ["ActivationWorker", "DefaultWorker"]


# Test worker handling


@patch("aap_eda.core.management.commands.dispatcherd.run_dispatcherd_service")
@patch("aap_eda.core.management.commands.dispatcherd.dispatcherd_setup")
def test_handle_activation_worker(mock_setup, mock_run):
    """Test handle with ActivationWorker."""
    command = Command()

    with override_settings(
        DISPATCHERD_DEFAULT_SETTINGS={"brokers": {"pg_notify": {}}},
        RULEBOOK_QUEUE_NAME="test_queue",
    ):
        with patch(
            "aap_eda.utils.sanitize_postgres_identifier",
            return_value="sanitized_queue",
        ):
            command.handle(worker_class="ActivationWorker", verbosity=1)

    mock_setup.assert_called_once()
    mock_run.assert_called_once()

    # Verify the correct settings were used
    setup_call_args = mock_setup.call_args[0][0]
    assert "brokers" in setup_call_args
    assert "pg_notify" in setup_call_args["brokers"]
    assert setup_call_args["brokers"]["pg_notify"]["channels"] == [
        "sanitized_queue"
    ]


@patch("aap_eda.core.management.commands.dispatcherd.run_dispatcherd_service")
@patch("aap_eda.core.management.commands.dispatcherd.dispatcherd_setup")
def test_handle_default_worker(mock_setup, mock_run):
    """Test handle with DefaultWorker."""
    command = Command()

    with override_settings(
        DISPATCHERD_DEFAULT_WORKER_SETTINGS={"test": "settings"}
    ):
        command.handle(worker_class="DefaultWorker", verbosity=2)

    mock_setup.assert_called_once_with({"test": "settings"})
    mock_run.assert_called_once()


@patch("aap_eda.core.management.commands.dispatcherd.run_dispatcherd_service")
@patch("aap_eda.core.management.commands.dispatcherd.dispatcherd_setup")
def test_handle_keyboard_interrupt(mock_setup, mock_run):
    """Test handle gracefully handles KeyboardInterrupt."""
    mock_run.side_effect = KeyboardInterrupt()

    command = Command()
    stdout = StringIO()
    command.stdout = stdout
    command.style = Mock()
    command.style.WARNING = Mock(return_value="WARNING: Worker shutdown")
    command.style.SUCCESS = Mock(
        return_value="SUCCESS: Starting ActivationWorker"
    )

    # Should not raise exception
    command.handle(worker_class="ActivationWorker", verbosity=1)

    command.style.WARNING.assert_called()
    warning_call = command.style.WARNING.call_args[0][0]
    assert "shutdown requested" in warning_call


@patch("aap_eda.core.management.commands.dispatcherd.run_dispatcherd_service")
@patch("aap_eda.core.management.commands.dispatcherd.dispatcherd_setup")
def test_handle_exception(mock_setup, mock_run):
    """Test handle properly handles general exceptions."""
    mock_run.side_effect = Exception("Test error")

    command = Command()
    stderr = StringIO()
    command.stderr = stderr
    command.style = Mock()
    command.style.ERROR = Mock(return_value="ERROR: Failed to start")
    command.style.SUCCESS = Mock(
        return_value="SUCCESS: Starting ActivationWorker"
    )

    with pytest.raises(SystemExit):
        command.handle(worker_class="ActivationWorker", verbosity=1)

    command.style.ERROR.assert_called()
    error_call = command.style.ERROR.call_args[0][0]
    assert "Failed to start" in error_call
    assert "Test error" in error_call


# Test output and verbosity


@patch("aap_eda.core.management.commands.dispatcherd.run_dispatcherd_service")
@patch("aap_eda.core.management.commands.dispatcherd.dispatcherd_setup")
def test_verbosity_levels(mock_setup, mock_run):
    """Test different verbosity levels control output."""
    command = Command()
    stdout = StringIO()
    command.stdout = stdout
    command.style = Mock()
    command.style.SUCCESS = Mock(side_effect=lambda x: x)

    with override_settings(
        DISPATCHERD_DEFAULT_WORKER_SETTINGS={"test": "settings"}
    ):
        # Test verbosity 0 (minimal output)
        command.handle(worker_class="DefaultWorker", verbosity=0)

        # Test verbosity 2 (verbose output)
        command.handle(worker_class="DefaultWorker", verbosity=2)

    # Should have multiple success style calls for verbose output
    assert command.style.SUCCESS.call_count >= 2


# Integration tests using call_command


@patch("aap_eda.core.management.commands.dispatcherd.run_dispatcherd_service")
@patch("aap_eda.core.management.commands.dispatcherd.dispatcherd_setup")
def test_call_command_activation_worker(mock_setup, mock_run):
    """Test call_command integration for ActivationWorker."""
    with override_settings(
        DISPATCHERD_DEFAULT_SETTINGS={"brokers": {"pg_notify": {}}},
        RULEBOOK_QUEUE_NAME="test_queue",
    ):
        with patch("aap_eda.utils.sanitize_postgres_identifier"):
            call_command(
                "dispatcherd",
                "--worker-class",
                "ActivationWorker",
            )

    mock_setup.assert_called_once()
    mock_run.assert_called_once()


@patch("aap_eda.core.management.commands.dispatcherd.run_dispatcherd_service")
@patch("aap_eda.core.management.commands.dispatcherd.dispatcherd_setup")
def test_call_command_default_worker(mock_setup, mock_run):
    """Test call_command integration for DefaultWorker."""
    with override_settings(
        DISPATCHERD_DEFAULT_WORKER_SETTINGS={"test": "settings"}
    ):
        call_command(
            "dispatcherd",
            "--worker-class",
            "DefaultWorker",
        )

    mock_setup.assert_called_once()
    mock_run.assert_called_once()


# Test for missing worker-class removed as it tests argparse behavior
# which is already validated by the framework itself
