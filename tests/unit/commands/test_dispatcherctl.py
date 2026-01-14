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

import io
from unittest.mock import Mock, patch

import pytest
from django.core.management.base import CommandError

from aap_eda.core.management.commands import dispatcherctl


@patch("aap_eda.core.management.commands.dispatcherctl.startup_logging")
def test_command_init_calls_startup_logging(mock_startup_logging):
    """Test Command initialization calls startup_logging."""
    dispatcherctl.Command()
    mock_startup_logging.assert_called_once()


@patch(
    "aap_eda.core.management.commands.dispatcherctl."
    "_build_command_data_from_args"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
@patch(
    "aap_eda.core.management.commands.dispatcherctl."
    "get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.yaml")
def test_dispatcherctl_runs_control_with_generated_config(
    mock_yaml, mock_get_control, mock_setup, mock_build_data
):
    """Test dispatcherctl runs control commands with generated config."""
    command = dispatcherctl.Command()
    command.stdout = io.StringIO()

    data = {"foo": "bar"}
    mock_build_data.return_value = data

    control = Mock()
    control.control_with_reply.return_value = [{"status": "ok"}]
    mock_get_control.return_value = control
    mock_yaml.dump.return_value = "payload\n"

    with patch.object(
        dispatcherctl.settings,
        "DISPATCHERD_DEFAULT_SETTINGS",
        {"setting": "value"},
    ):
        command.handle(
            command="running",
            expected_replies=1,
        )

    mock_setup.assert_called_once_with({"setting": "value"})
    control.control_with_reply.assert_called_once_with(
        "running", data=data, expected_replies=1
    )
    assert command.stdout.getvalue() == "payload\n"


@patch(
    "aap_eda.core.management.commands.dispatcherctl."
    "_build_command_data_from_args"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
@patch(
    "aap_eda.core.management.commands.dispatcherctl."
    "get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.yaml")
def test_dispatcherctl_raises_when_replies_missing(
    mock_yaml, mock_get_control, mock_setup, mock_build_data
):
    """Test dispatcherctl raises error when expected replies missing."""
    command = dispatcherctl.Command()
    command.stdout = io.StringIO()

    mock_build_data.return_value = {}
    control = Mock()
    control.control_with_reply.return_value = [{"status": "ok"}]
    mock_get_control.return_value = control
    mock_yaml.dump.return_value = "- status: ok\n"

    with patch.object(
        dispatcherctl.settings, "DISPATCHERD_DEFAULT_SETTINGS", {}
    ):
        with pytest.raises(CommandError):
            command.handle(
                command="running",
                expected_replies=2,
            )

    control.control_with_reply.assert_called_once_with(
        "running", data={}, expected_replies=2
    )


def test_dispatcherctl_requires_command():
    """Test dispatcherctl requires command."""
    command = dispatcherctl.Command()

    with pytest.raises(CommandError, match="No dispatcher control command"):
        command.handle(
            command=None,
            expected_replies=1,
        )


@patch(
    "aap_eda.core.management.commands.dispatcherctl."
    "_build_command_data_from_args"
)
@patch("aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup")
@patch(
    "aap_eda.core.management.commands.dispatcherctl."
    "get_control_from_settings"
)
@patch("aap_eda.core.management.commands.dispatcherctl.yaml")
def test_argument_parsing_integration(
    mock_yaml, mock_get_control, mock_setup, mock_build_data
):
    """Test that arguments are correctly passed through to data builder."""
    command = dispatcherctl.Command()
    command.stdout = io.StringIO()

    mock_build_data.return_value = {"task": "test_task"}
    control = Mock()
    control.control_with_reply.return_value = [{"status": "cancelled"}]
    mock_get_control.return_value = control
    mock_yaml.dump.return_value = "status: cancelled\n"

    with patch.object(
        dispatcherctl.settings, "DISPATCHERD_DEFAULT_SETTINGS", {}
    ):
        command.handle(
            command="cancel",
            task="test_task",
            uuid="test-uuid-123",
            expected_replies=1,
        )

    # Verify data builder was called with correct command name
    mock_build_data.assert_called_once()
    call_args = mock_build_data.call_args[0]
    schema_namespace = call_args[0]
    command_name = call_args[1]

    assert command_name == "cancel"
    # Verify namespace contains our arguments (Django options removed)
    namespace_vars = vars(schema_namespace)
    assert "task" in namespace_vars
    assert "uuid" in namespace_vars
    assert namespace_vars["task"] == "test_task"
    assert namespace_vars["uuid"] == "test-uuid-123"
    # Verify Django options were removed
    assert "expected_replies" not in namespace_vars
