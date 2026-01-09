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

"""Tests for dispatcherctl debug command."""

from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from aap_eda.core.management.commands.dispatcherctl import Command

# Test Command class initialization


@patch("aap_eda.core.management.commands.dispatcherctl.startup_logging")
def test_command_init(mock_startup_logging):
    """Test Command initialization calls startup_logging."""
    Command()  # Instantiation triggers startup_logging
    mock_startup_logging.assert_called_once()


# Test argument parsing


@patch(
    "dispatcherd.service.control_tasks.__all__",
    ["status", "running", "workers"],
)
def test_add_arguments_structure():
    """Test add_arguments creates subparser structure with dynamic commands."""
    with patch("dispatcherd.service.control_tasks.status"), patch(
        "dispatcherd.service.control_tasks.running"
    ), patch("dispatcherd.service.control_tasks.workers"):
        command = Command()
        parser = Mock()
        subparsers_mock = Mock()
        parser.add_subparsers.return_value = subparsers_mock

        command.add_arguments(parser)

        # Verify subparsers were created
        assert parser.add_subparsers.called, "add_subparsers should be called"

        # Verify dynamic commands were added
        assert subparsers_mock.add_parser.call_count == 3
        call_args_list = [
            call.args[0] for call in subparsers_mock.add_parser.call_args_list
        ]
        assert "status" in call_args_list
        assert "running" in call_args_list
        assert "workers" in call_args_list


# Test debug command handling


@patch("dispatcherd.service.control_tasks.__all__", ["status"])
@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_debug_command_success(mock_setup, mock_get_control):
    """Test handle executes debug command successfully."""
    # Mock the control interface
    mock_control = Mock()
    mock_control.control_with_reply.return_value = [
        {"status": "running", "workers": 1}
    ]
    mock_get_control.return_value = mock_control

    command = Command()
    stdout = StringIO()
    command.stdout = stdout
    command.style = Mock()

    command.handle_debug_subcommand("status", expected_replies=1)

    # Verify setup and control were called
    mock_setup.assert_called_once()
    mock_get_control.assert_called_once()
    mock_control.control_with_reply.assert_called_once_with(
        command="status",
        data={},
        expected_replies=1,
    )

    # Verify output contains YAML data
    output = stdout.getvalue()
    assert "status: running" in output
    assert "workers: 1" in output


@patch("dispatcherd.service.control_tasks.__all__", ["workers"])
@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_debug_command_with_filters(mock_setup, mock_get_control):
    """Test handle executes debug command with task and uuid filters."""
    # Mock the control interface
    mock_control = Mock()
    mock_control.control_with_reply.return_value = [
        {"workers": {"task-123": "running"}}
    ]
    mock_get_control.return_value = mock_control

    command = Command()
    stdout = StringIO()
    command.stdout = stdout

    command.handle_debug_subcommand(
        "workers", task="mytask", uuid="task-123", expected_replies=1
    )

    # Verify control was called with proper filters
    mock_control.control_with_reply.assert_called_once_with(
        command="workers",
        data={"task": "mytask", "uuid": "task-123"},
        expected_replies=1,
    )


@patch("dispatcherd.service.control_tasks.__all__", ["set_log_level"])
@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_set_log_level_command(mock_setup, mock_get_control):
    """Test handle executes set_log_level command with required log level."""
    # Mock the control interface
    mock_control = Mock()
    mock_control.control_with_reply.return_value = [
        {"status": "log level set to DEBUG"}
    ]
    mock_get_control.return_value = mock_control

    command = Command()
    stdout = StringIO()
    command.stdout = stdout

    command.handle_debug_subcommand(
        "set_log_level", log_level="DEBUG", expected_replies=1
    )

    # Verify control was called with log level data
    mock_control.control_with_reply.assert_called_once_with(
        command="set_log_level",
        data={"level": "DEBUG"},
        expected_replies=1,
    )


@patch("dispatcherd.service.control_tasks.__all__", ["set_log_level"])
def test_handle_set_log_level_missing_level():
    """Test set_log_level command fails when log level is not provided."""
    command = Command()

    with pytest.raises(CommandError) as excinfo:
        command.handle_debug_subcommand("set_log_level", expected_replies=1)

    assert "--log-level is required for set_log_level command" in str(
        excinfo.value
    )


@patch("dispatcherd.service.control_tasks.__all__", ["status"])
@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_debug_command_insufficient_replies(
    mock_setup, mock_get_control
):
    """Test handle raises error when insufficient replies received."""
    # Mock the control interface to return fewer replies than expected
    mock_control = Mock()
    mock_control.control_with_reply.return_value = []  # No replies
    mock_get_control.return_value = mock_control

    command = Command()

    with pytest.raises(CommandError) as excinfo:
        command.handle_debug_subcommand("status", expected_replies=1)

    assert "dispatcherctl returned fewer replies than expected" in str(
        excinfo.value
    )


@patch("dispatcherd.service.control_tasks.__all__", ["status"])
@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_debug_command_multiple_replies(mock_setup, mock_get_control):
    """Test handle formats multiple replies correctly."""
    # Mock the control interface to return multiple replies
    mock_control = Mock()
    mock_control.control_with_reply.return_value = [
        {"node": "worker-1", "status": "running"},
        {"node": "worker-2", "status": "stopped"},
    ]
    mock_get_control.return_value = mock_control

    command = Command()
    stdout = StringIO()
    command.stdout = stdout

    command.handle_debug_subcommand("status", expected_replies=2)

    # Verify output contains formatted multiple replies
    output = stdout.getvalue()
    assert "reply-0:" in output
    assert "reply-1:" in output
    assert "worker-1" in output
    assert "worker-2" in output


@patch("dispatcherd.service.control_tasks.__all__", ["status"])
@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_debug_command_exception(mock_setup, mock_get_control):
    """Test handle properly handles debug command exceptions."""
    # Mock the control interface to raise an exception
    mock_get_control.side_effect = Exception("Connection failed")

    command = Command()

    with pytest.raises(CommandError) as excinfo:
        command.handle_debug_subcommand("status", expected_replies=1)

    assert "Command failed: Connection failed" in str(excinfo.value)


def test_handle_invalid_debug_command():
    """Test handle raises error for invalid debug commands."""
    with patch("dispatcherd.service.control_tasks.__all__", ["status"]):
        command = Command()

        with pytest.raises(CommandError) as excinfo:
            command.handle_debug_subcommand(
                "invalid_command", expected_replies=1
            )

        assert "Invalid debug command 'invalid_command'" in str(excinfo.value)
        assert "Must be one of: status" in str(excinfo.value)


@patch("dispatcherd.service.control_tasks.__all__", ["status", "workers"])
def test_handle_unknown_command():
    """Test handle with unknown debug command shows error message."""
    command = Command()
    stderr = StringIO()
    command.stderr = stderr
    command.style = Mock()
    command.style.ERROR = Mock(return_value="ERROR: Unknown command")

    with pytest.raises(CommandError):
        command.handle(command="invalid_command")

    command.style.ERROR.assert_called()
    error_call = command.style.ERROR.call_args[0][0]
    assert "Unknown debug command 'invalid_command'" in error_call
    assert "status, workers" in error_call


@patch(
    "dispatcherd.service.control_tasks.__all__",
    ["status", "workers", "running"],
)
def test_handle_no_subcommand():
    """Test handle shows available commands when no subcommand provided."""
    command = Command()
    stdout = StringIO()
    command.stdout = stdout
    command.style = Mock()
    command.style.SUCCESS = Mock(return_value="Available commands")

    command.handle(command=None)

    command.style.SUCCESS.assert_called()
    success_call = command.style.SUCCESS.call_args[0][0]
    assert "Available debug commands: status, workers, running" in success_call
    assert "aap-eda-manage dispatcherctl <command>" in success_call
    assert (
        "Note: Debug commands require a running dispatcher service"
        in success_call
    )


@patch("dispatcherd.service.control_tasks.__all__", ["status"])
@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_integration(mock_setup, mock_get_control):
    """Test full handle method integration with debug command routing."""
    # Mock the control interface
    mock_control = Mock()
    mock_control.control_with_reply.return_value = [
        {"status": "service active"}
    ]
    mock_get_control.return_value = mock_control

    command = Command()
    stdout = StringIO()
    command.stdout = stdout

    command.handle(command="status", expected_replies=1)

    # Verify the full flow worked
    mock_setup.assert_called_once()
    mock_control.control_with_reply.assert_called_once()
    assert "status: service active" in stdout.getvalue()


# Integration tests using call_command


@patch("dispatcherd.service.control_tasks.__all__", ["status"])
@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_call_command_debug(mock_setup, mock_get_control):
    """Test call_command integration for debug commands."""
    # Mock the control interface
    mock_control = Mock()
    mock_control.control_with_reply.return_value = [{"service": "running"}]
    mock_get_control.return_value = mock_control

    # Should not raise exception
    call_command("dispatcherctl", "status")

    mock_control.control_with_reply.assert_called_once()


@patch("dispatcherd.service.control_tasks.__all__", ["status", "workers"])
def test_call_command_no_args():
    """Test call_command with no arguments shows help."""
    # Should not raise exception
    call_command("dispatcherctl")
    # Test passes if no exception is raised
