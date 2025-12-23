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

"""Tests for dispatcherctl management command."""

from io import StringIO
from unittest.mock import Mock, patch

import pytest
import yaml
from dispatcherd.service import control_tasks
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from aap_eda.core.management.commands.dispatcherctl import (
    DEFAULT_OUTPUT_FORMAT,
    Command,
    format_output_yaml,
)

# Test utility functions


def test_format_output_yaml():
    """Test format_output_yaml function."""
    data = {"key": "value", "number": 42}
    result = format_output_yaml(data)
    expected = yaml.dump(data, default_flow_style=False)
    assert result == expected


# Test Command class initialization


@patch("aap_eda.core.management.commands.dispatcherctl.startup_logging")
def test_command_init(mock_startup_logging):
    """Test Command initialization calls startup_logging."""
    Command()  # Instantiation triggers startup_logging
    mock_startup_logging.assert_called_once()


# Test argument parsing


def test_add_arguments_structure():
    """Test that add_arguments creates proper subparser structure."""
    command = Command()
    parser = Mock()
    subparsers_mock = Mock()
    parser.add_subparsers.return_value = subparsers_mock

    command.add_arguments(parser)

    # Verify subparsers were created (flexible check since impl varies)
    assert parser.add_subparsers.called, "add_subparsers should be called"

    # Verify activate subcommand was added (flexible check for activate call)
    activate_calls = [
        call_obj
        for call_obj in subparsers_mock.add_parser.call_args_list
        if len(call_obj[0]) > 0 and call_obj[0][0] == "activate"
    ]
    assert len(activate_calls) > 0, "Activate subcommand should be added"

    # Verify debug commands were added (flexible check)
    available_commands = list(control_tasks.__all__)
    command_calls = [
        call_obj
        for call_obj in subparsers_mock.add_parser.call_args_list
        if len(call_obj[0]) > 0 and call_obj[0][0] in available_commands
    ]
    assert len(command_calls) >= len(
        available_commands
    ), "All debug commands should be added"


# Test activate subcommand handling


@patch(
    "aap_eda.core.management.commands.dispatcherctl.run_dispatcherd_service"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_worker_subcommand_activation_worker(mock_setup, mock_run):
    """Test handle_worker_subcommand with ActivationWorker."""
    command = Command()

    with override_settings(
        DISPATCHERD_DEFAULT_SETTINGS={"brokers": {"pg_notify": {}}},
        RULEBOOK_QUEUE_NAME="test_queue",
    ):
        with patch(
            "aap_eda.utils.sanitize_postgres_identifier",
            return_value="sanitized_queue",
        ):
            command.handle_worker_subcommand(
                worker_type="ActivationWorker", verbosity=1
            )

    mock_setup.assert_called_once()
    mock_run.assert_called_once()


@patch(
    "aap_eda.core.management.commands.dispatcherctl.run_dispatcherd_service"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_worker_subcommand_default_worker(mock_setup, mock_run):
    """Test handle_worker_subcommand with DefaultWorker."""
    command = Command()

    with override_settings(
        DISPATCHERD_DEFAULT_WORKER_SETTINGS={"test": "settings"}
    ):
        command.handle_worker_subcommand(
            worker_type="DefaultWorker", verbosity=2
        )

    mock_setup.assert_called_once()
    mock_run.assert_called_once()


@patch(
    "aap_eda.core.management.commands.dispatcherctl.run_dispatcherd_service"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_worker_subcommand_keyboard_interrupt(mock_setup, mock_run):
    """Test handle_worker_subcommand handles KeyboardInterrupt."""
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
    command.handle_worker_subcommand(
        worker_type="ActivationWorker", log_level="INFO", verbosity=1
    )

    command.style.WARNING.assert_called()


@patch(
    "aap_eda.core.management.commands.dispatcherctl.run_dispatcherd_service"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_worker_subcommand_exception(mock_setup, mock_run):
    """Test handle_worker_subcommand handles general exceptions."""
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
        command.handle_worker_subcommand(
            worker_type="ActivationWorker", log_level="INFO", verbosity=1
        )

    command.style.ERROR.assert_called()


# Test debug subcommand handling


@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_debug_subcommand_success(mock_setup, mock_get_control):
    """Test handle_debug_subcommand successful execution."""
    # Setup mocks
    mock_control = Mock()
    mock_control.control_with_reply.return_value = [
        {"status": "running", "workers": 2}
    ]
    mock_get_control.return_value = mock_control

    command = Command()
    stdout = StringIO()
    command.stdout = stdout

    command.handle_debug_subcommand(
        command="status",
        task=None,
        uuid=None,
        output_format="yaml",
        expected_replies=1,
    )

    mock_setup.assert_called_once()
    mock_get_control.assert_called_once()
    mock_control.control_with_reply.assert_called_once_with(
        command="status", data={}, expected_replies=1
    )


@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_debug_subcommand_with_filters(mock_setup, mock_get_control):
    """Test handle_debug_subcommand with task and uuid filters."""
    mock_control = Mock()
    mock_control.control_with_reply.return_value = [{"filtered": "result"}]
    mock_get_control.return_value = mock_control

    command = Command()
    stdout = StringIO()
    command.stdout = stdout

    command.handle_debug_subcommand(
        command="workers",
        task="test_task",
        uuid="test-uuid-123",
        expected_replies=1,
    )

    mock_control.control_with_reply.assert_called_once_with(
        command="workers",
        data={"task": "test_task", "uuid": "test-uuid-123"},
        expected_replies=1,
    )


@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_debug_subcommand_multiple_replies(
    mock_setup, mock_get_control
):
    """Test handle_debug_subcommand with multiple replies."""
    mock_control = Mock()
    mock_control.control_with_reply.return_value = [
        {"worker": 1, "status": "active"},
        {"worker": 2, "status": "idle"},
    ]
    mock_get_control.return_value = mock_control

    command = Command()
    stdout = StringIO()
    command.stdout = stdout

    command.handle_debug_subcommand(command="workers", expected_replies=2)

    output = stdout.getvalue()
    assert "reply-0" in output
    assert "reply-1" in output


@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_debug_subcommand_insufficient_replies(
    mock_setup, mock_get_control
):
    """Test handle_debug_subcommand with insufficient replies."""
    mock_control = Mock()
    mock_control.control_with_reply.return_value = [{"single": "reply"}]
    mock_get_control.return_value = mock_control

    command = Command()
    stderr = StringIO()
    command.stderr = stderr
    command.style = Mock()
    command.style.ERROR = Mock(
        return_value="ERROR: Only 1 of 3 expected replies"
    )

    with pytest.raises(CommandError):
        command.handle_debug_subcommand(command="status", expected_replies=3)


@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_debug_subcommand_connection_error(
    mock_setup, mock_get_control
):
    """Test handle_debug_subcommand with ConnectionError."""
    mock_control = Mock()
    mock_control.control_with_reply.side_effect = ConnectionError(
        "Cannot connect"
    )
    mock_get_control.return_value = mock_control

    command = Command()
    stderr = StringIO()
    command.stderr = stderr
    command.style = Mock()
    command.style.ERROR = Mock(return_value="ERROR: Cannot connect")

    with pytest.raises(CommandError):
        command.handle_debug_subcommand(command="status")


@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_debug_subcommand_general_exception(
    mock_setup, mock_get_control
):
    """Test handle_debug_subcommand with general exception."""
    mock_setup.side_effect = Exception("Setup failed")

    command = Command()
    stderr = StringIO()
    command.stderr = stderr
    command.style = Mock()
    command.style.ERROR = Mock(return_value="ERROR: Command failed")

    with pytest.raises(CommandError):
        command.handle_debug_subcommand(command="status")


# Test set_log_level command


@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_set_log_level_subcommand_success(mock_setup, mock_get_control):
    """Test handle_debug_subcommand for set_log_level command."""
    mock_control = Mock()
    mock_control.control_with_reply.return_value = [
        {"logger": "dispatcherd", "level": "DEBUG", "previous_level": "INFO"}
    ]
    mock_get_control.return_value = mock_control

    command = Command()
    stdout = StringIO()
    command.stdout = stdout

    command.handle_debug_subcommand(
        command="set_log_level",
        command_log_level="INFO",
        log_level="DEBUG",
        output_format="yaml",
        expected_replies=1,
    )

    mock_control.control_with_reply.assert_called_once_with(
        command="set_log_level", data={"level": "DEBUG"}, expected_replies=1
    )


@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_handle_set_log_level_missing_level(mock_setup):
    """Test handle_debug_subcommand for set_log_level without level."""
    command = Command()
    stderr = StringIO()
    command.stderr = stderr
    command.style = Mock()
    command.style.ERROR = Mock(return_value="ERROR: --log-level is required")

    with pytest.raises(CommandError):
        command.handle_debug_subcommand(
            command="set_log_level",
            command_log_level="INFO",
            log_level=None,  # Missing level
            output_format="yaml",
            expected_replies=1,
        )


# Test main handle method


def test_handle_activate_subcommand():
    """Test handle routes to activate subcommand."""
    command = Command()

    with patch.object(command, "handle_worker_subcommand") as mock_handle:
        command.handle(command="activate", worker_type="ActivationWorker")
        mock_handle.assert_called_once()


def test_handle_debug_subcommand():
    """Test handle routes to debug subcommands."""
    command = Command()

    for cmd in list(control_tasks.__all__):
        with patch.object(command, "handle_debug_subcommand") as mock_handle:
            command.handle(command=cmd)
            # command parameter is filtered out to avoid duplicate argument
            mock_handle.assert_called_once_with(cmd)


def test_handle_unknown_subcommand():
    """Test handle with unknown subcommand."""
    command = Command()
    stderr = StringIO()
    command.stderr = stderr
    command.style = Mock()
    command.style.ERROR = Mock(return_value="ERROR: Unknown subcommand")

    with pytest.raises(CommandError):
        command.handle(command="unknown")


# Integration tests using call_command


@patch(
    "aap_eda.core.management.commands.dispatcherctl.run_dispatcherd_service"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_call_command_activate_activation(mock_setup, mock_run):
    """Test call_command integration for activate subcommand."""
    with override_settings(
        DISPATCHERD_DEFAULT_SETTINGS={"brokers": {"pg_notify": {}}},
        RULEBOOK_QUEUE_NAME="test_queue",
    ):
        with patch("aap_eda.utils.sanitize_postgres_identifier"):
            call_command(
                "dispatcherctl",
                "activate",
                "--worker-type",
                "ActivationWorker",
            )

    mock_setup.assert_called_once()
    mock_run.assert_called_once()


@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_call_command_debug_status(mock_setup, mock_get_control):
    """Test call_command integration for debug status command."""
    mock_control = Mock()
    mock_control.control_with_reply.return_value = [{"status": "ok"}]
    mock_get_control.return_value = mock_control

    # Capture stdout
    stdout = StringIO()
    call_command("dispatcherctl", "status", stdout=stdout)

    mock_setup.assert_called_once()
    mock_control.control_with_reply.assert_called_once()

    # Should have YAML output
    output = stdout.getvalue()
    assert "status: ok" in output


@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_call_command_debug_with_options(mock_setup, mock_get_control):
    """Test call_command with debug options."""
    mock_control = Mock()
    mock_control.control_with_reply.return_value = [
        {"result": "filtered"},
        {"result": "filtered2"},
    ]
    mock_get_control.return_value = mock_control

    stdout = StringIO()
    call_command(
        "dispatcherctl",
        "workers",
        "--task",
        "test_task",
        "--uuid",
        "test-uuid",
        "--expected-replies",
        "2",
        stdout=stdout,
    )

    mock_control.control_with_reply.assert_called_once_with(
        command="workers",
        data={"task": "test_task", "uuid": "test-uuid"},
        expected_replies=2,
    )

    # Should have YAML output
    output = stdout.getvalue()
    parsed = yaml.safe_load(output)
    assert parsed["reply-0"]["result"] == "filtered"
    assert parsed["reply-1"]["result"] == "filtered2"


@patch(
    "aap_eda.core.management.commands.dispatcherctl.get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
def test_call_command_set_log_level(mock_setup, mock_get_control):
    """Test call_command integration for set_log_level command."""
    mock_control = Mock()
    mock_control.control_with_reply.return_value = [
        {"logger": "dispatcherd", "level": "DEBUG", "previous_level": "INFO"}
    ]
    mock_get_control.return_value = mock_control

    stdout = StringIO()
    call_command(
        "dispatcherctl",
        "set_log_level",
        "--log-level",
        "DEBUG",
        stdout=stdout,
    )

    mock_control.control_with_reply.assert_called_once_with(
        command="set_log_level", data={"level": "DEBUG"}, expected_replies=1
    )

    # Should have YAML output
    output = stdout.getvalue()
    parsed = yaml.safe_load(output)
    assert parsed["logger"] == "dispatcherd"
    assert parsed["level"] == "DEBUG"
    assert parsed["previous_level"] == "INFO"


# Test constants and configuration


def test_control_tasks_available():
    """Test control_tasks.__all__ returns expected debug commands."""
    commands = list(control_tasks.__all__)

    # Verify it returns a list
    assert isinstance(commands, list)

    # Verify it contains essential commands (fallback or dynamic)
    essential_commands = {"running", "workers", "status", "alive"}
    assert essential_commands.issubset(set(commands))

    # Verify all commands are strings
    assert all(isinstance(cmd, str) for cmd in commands)


def test_default_output_format_constant():
    """Test DEFAULT_OUTPUT_FORMAT is yaml."""
    assert DEFAULT_OUTPUT_FORMAT == "yaml"


# Test error conditions and edge cases


def test_format_output_none_data():
    """Test format_output_yaml with None data."""
    result = format_output_yaml(None)
    assert result == "null\n...\n"


@patch("aap_eda.core.management.commands.dispatcherctl.logger")
def test_debug_command_logging_on_exception(mock_logger):
    """Test that exceptions in debug commands are logged with exc_info."""
    command = Command()
    stderr = StringIO()
    command.stderr = stderr
    command.style = Mock()
    command.style.ERROR = Mock(return_value="ERROR: Command failed")

    with patch(
        "aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup",
        side_effect=Exception("Test error"),
    ):
        with pytest.raises(CommandError):
            command.handle_debug_subcommand(command="status")

    # Verify logger.error was called with exc_info=True and the specific error
    mock_logger.error.assert_called_once_with(
        "Unexpected dispatcherctl debug command error: Test error",
        exc_info=True,
    )
