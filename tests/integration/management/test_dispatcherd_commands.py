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

"""Integration tests for dispatcherd management commands."""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

#################################################################
# Tests for dispatcherd command
#################################################################


@pytest.mark.django_db
def test_dispatcherd_command_activation_worker():
    """Test dispatcherd command with ActivationWorker."""
    with patch(
        "aap_eda.core.management.commands.dispatcherd.dispatcherd_setup"
    ) as mock_setup:
        with patch(
            "aap_eda.core.management.commands.dispatcherd."
            "run_dispatcherd_service"
        ) as mock_run:
            with patch(
                "aap_eda.core.management.commands.dispatcherd.startup_logging"
            ) as mock_logging:
                stdout = StringIO()

                call_command(
                    "dispatcherd",
                    "--worker-class=ActivationWorker",
                    stdout=stdout,
                )

                # Verify startup logging was called
                mock_logging.assert_called_once()

                # Verify configuration was set up with sanitized queue name
                mock_setup.assert_called_once()
                setup_call_args = mock_setup.call_args[0][0]

                assert "brokers" in setup_call_args
                assert "pg_notify" in setup_call_args["brokers"]
                assert "channels" in setup_call_args["brokers"]["pg_notify"]

                # Verify run_service was called
                mock_run.assert_called_once()

                # Verify output message
                output = stdout.getvalue()
                assert "Starting ActivationWorker with dispatcherd." in output


@pytest.mark.django_db
def test_dispatcherd_command_default_worker():
    """Test dispatcherd command with DefaultWorker."""
    with patch(
        "aap_eda.core.management.commands.dispatcherd.dispatcherd_setup"
    ) as mock_setup:
        with patch(
            "aap_eda.core.management.commands.dispatcherd."
            "run_dispatcherd_service"
        ) as mock_run:
            stdout = StringIO()

            call_command(
                "dispatcherd",
                "--worker-class=DefaultWorker",
                stdout=stdout,
            )

            # Verify configuration was set up with default worker settings
            mock_setup.assert_called_once()

            # Verify run_service was called
            mock_run.assert_called_once()

            # Verify output message
            output = stdout.getvalue()
            assert "Starting DefaultWorker with dispatcherd." in output


@pytest.mark.django_db
def test_dispatcherd_command_verbosity_levels():
    """Test dispatcherd command with different verbosity levels."""
    with patch(
        "aap_eda.core.management.commands.dispatcherd.dispatcherd_setup"
    ):
        with patch(
            "aap_eda.core.management.commands.dispatcherd."
            "run_dispatcherd_service"
        ):
            # Test verbosity 0 (minimal output)
            stdout = StringIO()
            call_command(
                "dispatcherd",
                "--worker-class=DefaultWorker",
                verbosity=0,
                stdout=stdout,
            )
            output = stdout.getvalue()
            assert output == ""  # No output at verbosity 0

            # Test verbosity 1 (normal output)
            stdout = StringIO()
            call_command(
                "dispatcherd",
                "--worker-class=DefaultWorker",
                verbosity=1,
                stdout=stdout,
            )
            output = stdout.getvalue()
            assert "Starting DefaultWorker with dispatcherd." in output
            assert "Worker type:" not in output

            # Test verbosity 2 (detailed output)
            stdout = StringIO()
            call_command(
                "dispatcherd",
                "--worker-class=DefaultWorker",
                verbosity=2,
                stdout=stdout,
            )
            output = stdout.getvalue()
            assert "Starting DefaultWorker with dispatcherd." in output
            assert "Worker type: DefaultWorker" in output


@pytest.mark.django_db
def test_dispatcherd_command_missing_worker_class():
    """Test dispatcherd command with missing worker class argument."""
    with pytest.raises(CommandError):
        # Missing required --worker-class argument should cause CommandError
        call_command("dispatcherd")


@pytest.mark.django_db
def test_dispatcherd_command_invalid_worker_class():
    """Test dispatcherd command with invalid worker class."""
    with pytest.raises(CommandError):
        # Invalid worker class should cause CommandError
        call_command("dispatcherd", "--worker-class=InvalidWorker")


@pytest.mark.django_db
@patch("aap_eda.core.management.commands.dispatcherd.logger")
def test_dispatcherd_command_keyboard_interrupt(mock_logger):
    """Test dispatcherd command handling KeyboardInterrupt."""
    with patch(
        "aap_eda.core.management.commands.dispatcherd.dispatcherd_setup"
    ):
        with patch(
            "aap_eda.core.management.commands.dispatcherd."
            "run_dispatcherd_service",
            side_effect=KeyboardInterrupt(),
        ):
            stdout = StringIO()

            call_command(
                "dispatcherd",
                "--worker-class=DefaultWorker",
                stdout=stdout,
            )

            # Verify warning output and logging
            output = stdout.getvalue()
            assert "DefaultWorker shutdown requested." in output
            mock_logger.info.assert_called_with(
                "DefaultWorker shutdown requested."
            )


@pytest.mark.django_db
@patch("aap_eda.core.management.commands.dispatcherd.logger")
def test_dispatcherd_command_general_exception(mock_logger):
    """Test dispatcherd command handling general exceptions."""
    with patch(
        "aap_eda.core.management.commands.dispatcherd.dispatcherd_setup"
    ):
        with patch(
            "aap_eda.core.management.commands.dispatcherd."
            "run_dispatcherd_service",
            side_effect=RuntimeError("Service failed"),
        ):
            stderr = StringIO()

            with pytest.raises(SystemExit) as exc_info:
                call_command(
                    "dispatcherd",
                    "--worker-class=DefaultWorker",
                    stderr=stderr,
                )

            # Verify SystemExit with code 1
            assert exc_info.value.code == 1

            # Verify error output and logging
            error_output = stderr.getvalue()
            assert (
                "Failed to start DefaultWorker: Service failed" in error_output
            )
            mock_logger.error.assert_called_with(
                "Failed to start DefaultWorker: Service failed", exc_info=True
            )


@pytest.mark.django_db
@override_settings(
    RULEBOOK_QUEUE_NAME="test_queue",
    DISPATCHERD_DEFAULT_SETTINGS={
        "brokers": {"pg_notify": {"database_url": "test://"}},
        "other_setting": "value",
    },
)
def test_dispatcherd_command_activation_worker_settings():
    """Test ActivationWorker configuration with queue sanitization."""
    with patch(
        "aap_eda.core.management.commands.dispatcherd.dispatcherd_setup"
    ) as mock_setup:
        with patch(
            "aap_eda.core.management.commands.dispatcherd."
            "run_dispatcherd_service"
        ):
            with patch(
                "aap_eda.utils.sanitize_postgres_identifier"
            ) as mock_sanitize:
                mock_sanitize.return_value = "sanitized_test_queue"

                call_command(
                    "dispatcherd",
                    "--worker-class=ActivationWorker",
                    stdout=StringIO(),
                )

                # Verify sanitization was called
                mock_sanitize.assert_called_once_with("test_queue")

                # Verify settings were merged correctly
                mock_setup.assert_called_once()
                setup_call_args = mock_setup.call_args[0][0]

                assert setup_call_args["other_setting"] == "value"
                assert (
                    setup_call_args["brokers"]["pg_notify"]["channels"][0]
                    == "sanitized_test_queue"
                )


@pytest.mark.django_db
@override_settings(
    DISPATCHERD_DEFAULT_WORKER_SETTINGS={"test_setting": "test_value"}
)
def test_dispatcherd_command_default_worker_settings():
    """Test DefaultWorker configuration with default settings."""
    with patch(
        "aap_eda.core.management.commands.dispatcherd.dispatcherd_setup"
    ) as mock_setup:
        with patch(
            "aap_eda.core.management.commands.dispatcherd."
            "run_dispatcherd_service"
        ):
            call_command(
                "dispatcherd",
                "--worker-class=DefaultWorker",
                stdout=StringIO(),
            )

            # Verify default worker settings were used
            mock_setup.assert_called_once_with({"test_setting": "test_value"})


#################################################################
# Tests for dispatcherctl command
#################################################################


@pytest.mark.django_db
def test_dispatcherctl_command_valid_command():
    """Test dispatcherctl command with valid command execution."""
    with patch(
        "aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup"
    ) as mock_setup:
        with patch(
            "aap_eda.core.management.commands.dispatcherctl."
            "get_control_from_settings"
        ) as mock_get_control:
            mock_control = MagicMock()
            mock_control.control_with_reply.return_value = [
                {"status": "success"}
            ]
            mock_get_control.return_value = mock_control

            stdout = StringIO()
            call_command(
                "dispatcherctl",
                "status",
                stdout=stdout,
            )

            # Verify setup was called
            mock_setup.assert_called_once()

            # Verify control interface was used
            mock_get_control.assert_called_once()
            mock_control.control_with_reply.assert_called_once()

            # Verify YAML output
            output = stdout.getvalue()
            assert "status: success" in output


@pytest.mark.django_db
def test_dispatcherctl_command_missing_command():
    """Test dispatcherctl command with missing command argument."""
    with patch(
        "aap_eda.core.management.commands.dispatcherctl.control_tasks"
    ) as mock_tasks:
        mock_tasks.__all__ = ["status", "info"]

        with pytest.raises(CommandError):
            # Missing command argument should cause CommandError
            call_command("dispatcherctl")


@pytest.mark.django_db
def test_dispatcherctl_command_insufficient_replies():
    """Test dispatcherctl command with insufficient replies."""
    with patch(
        "aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup"
    ):
        with patch(
            "aap_eda.core.management.commands.dispatcherctl."
            "get_control_from_settings"
        ) as mock_get_control:
            mock_control = MagicMock()
            # Return fewer replies than expected
            mock_control.control_with_reply.return_value = []
            mock_get_control.return_value = mock_control

            with pytest.raises(CommandError) as exc_info:
                call_command(
                    "dispatcherctl",
                    "status",
                    expected_replies=1,
                    stdout=StringIO(),
                )

            assert "dispatcherctl returned fewer replies than expected" in str(
                exc_info.value
            )


@pytest.mark.django_db
@patch("aap_eda.core.management.commands.dispatcherctl.logger")
def test_dispatcherctl_command_keyboard_interrupt(mock_logger):
    """Test dispatcherctl command handling KeyboardInterrupt."""
    with patch(
        "aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup"
    ):
        with patch(
            "aap_eda.core.management.commands.dispatcherctl."
            "get_control_from_settings",
            side_effect=KeyboardInterrupt(),
        ):
            with pytest.raises(CommandError) as exc_info:
                call_command(
                    "dispatcherctl",
                    "status",
                    stdout=StringIO(),
                )

            assert "Command interrupted by user" in str(exc_info.value)
            mock_logger.info.assert_called_with(
                "Received interrupt signal, shutting down dispatcherctl"
            )


@pytest.mark.django_db
@patch("aap_eda.core.management.commands.dispatcherctl.logger")
def test_dispatcherctl_command_general_exception(mock_logger):
    """Test dispatcherctl command handling general exceptions."""
    with patch(
        "aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup"
    ):
        with patch(
            "aap_eda.core.management.commands.dispatcherctl."
            "get_control_from_settings",
            side_effect=RuntimeError("Control failed"),
        ):
            with pytest.raises(CommandError) as exc_info:
                call_command(
                    "dispatcherctl",
                    "status",
                    stdout=StringIO(),
                )

            assert "Failed to execute status: Control failed" in str(
                exc_info.value
            )
            mock_logger.error.assert_called_with(
                "Failed to execute status: Control failed", exc_info=True
            )


@pytest.mark.django_db
def test_dispatcherctl_command_django_options_removal():
    """Test that Django-specific options are removed properly."""
    with patch(
        "aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup"
    ):
        with patch(
            "aap_eda.core.management.commands.dispatcherctl."
            "get_control_from_settings"
        ) as mock_get_control:
            with patch(
                "aap_eda.core.management.commands.dispatcherctl."
                "_build_command_data_from_args"
            ) as mock_build_data:
                mock_control = MagicMock()
                mock_control.control_with_reply.return_value = [
                    {"result": "ok"}
                ]
                mock_get_control.return_value = mock_control
                mock_build_data.return_value = {}

                call_command(
                    "dispatcherctl",
                    "status",
                    verbosity=2,
                    traceback=True,
                    no_color=True,
                    stdout=StringIO(),
                )

                # Verify Django options were removed from data building
                build_call_args = mock_build_data.call_args[0][0]
                for django_opt in (
                    "verbosity",
                    "traceback",
                    "no_color",
                    "force_color",
                    "skip_checks",
                ):
                    assert not hasattr(build_call_args, django_opt)


@pytest.mark.django_db
def test_dispatcherctl_command_expected_replies_handling():
    """Test dispatcherctl command with custom expected_replies."""
    with patch(
        "aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup"
    ):
        with patch(
            "aap_eda.core.management.commands.dispatcherctl."
            "get_control_from_settings"
        ) as mock_get_control:
            mock_control = MagicMock()
            mock_control.control_with_reply.return_value = [
                {"reply1": "data"},
                {"reply2": "data"},
            ]
            mock_get_control.return_value = mock_control

            call_command(
                "dispatcherctl",
                "status",
                expected_replies=2,
                stdout=StringIO(),
            )

            # Verify control was called with expected_replies parameter
            call_args = mock_control.control_with_reply.call_args[1]
            assert call_args["expected_replies"] == 2


@pytest.mark.django_db
@override_settings(
    DISPATCHERD_DEFAULT_SETTINGS={"control_setting": "test_value"}
)
@patch("aap_eda.core.management.commands.dispatcherctl.logger")
def test_dispatcherctl_command_settings_integration(mock_logger):
    """Test dispatcherctl configuration with Django settings."""
    with patch(
        "aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup"
    ) as mock_setup:
        with patch(
            "aap_eda.core.management.commands.dispatcherctl."
            "get_control_from_settings"
        ) as mock_get_control:
            mock_control = MagicMock()
            mock_control.control_with_reply.return_value = [{"ok": True}]
            mock_get_control.return_value = mock_control

            call_command(
                "dispatcherctl",
                "status",
                stdout=StringIO(),
            )

            # Verify settings were used
            mock_setup.assert_called_once_with(
                {"control_setting": "test_value"}
            )

            # Verify logging message
            mock_logger.info.assert_called_with(
                "Using config generated from "
                "settings.DISPATCHERD_DEFAULT_SETTINGS"
            )


#################################################################
# Tests for command initialization and logging
#################################################################


@pytest.mark.django_db
def test_dispatcherd_command_initialization():
    """Test dispatcherd command initialization and startup logging."""
    with patch(
        "aap_eda.core.management.commands.dispatcherd.startup_logging"
    ) as mock_logging:
        from aap_eda.core.management.commands.dispatcherd import (
            Command as DispatcherdCommand,
        )

        # Command initialization should call startup_logging
        DispatcherdCommand()
        mock_logging.assert_called_once()


@pytest.mark.django_db
def test_dispatcherctl_command_initialization():
    """Test dispatcherctl command initialization and startup logging."""
    with patch(
        "aap_eda.core.management.commands.dispatcherctl.startup_logging"
    ) as mock_logging:
        from aap_eda.core.management.commands.dispatcherctl import (
            Command as DispatcherctlCommand,
        )

        # Command initialization should call startup_logging
        DispatcherctlCommand()
        mock_logging.assert_called_once()


#################################################################
# Tests for command argument registration
#################################################################


@pytest.mark.django_db
def test_dispatcherd_command_arguments():
    """Test dispatcherd command argument registration and validation."""
    with patch(
        "aap_eda.core.management.commands.dispatcherd.dispatcherd_setup"
    ):
        with patch(
            "aap_eda.core.management.commands.dispatcherd."
            "run_dispatcherd_service"
        ):
            # Test valid worker class arguments work
            call_command(
                "dispatcherd",
                "--worker-class=ActivationWorker",
                stdout=StringIO(),
            )

            call_command(
                "dispatcherd",
                "--worker-class=DefaultWorker",
                stdout=StringIO(),
            )

            # Invalid worker class should raise CommandError (tested above)


@pytest.mark.django_db
def test_dispatcherctl_command_subcommands():
    """Test dispatcherctl command subcommand functionality."""
    with patch(
        "aap_eda.core.management.commands.dispatcherctl.control_tasks"
    ) as mock_tasks:
        mock_tasks.__all__ = ["status", "info"]

        with patch(
            "aap_eda.core.management.commands.dispatcherctl.dispatcherd_setup"
        ):
            with patch(
                "aap_eda.core.management.commands.dispatcherctl."
                "get_control_from_settings"
            ) as mock_get_control:
                mock_control = MagicMock()
                mock_control.control_with_reply.return_value = [{"ok": True}]
                mock_get_control.return_value = mock_control

                # Test that status command executes
                call_command(
                    "dispatcherctl",
                    "status",
                    stdout=StringIO(),
                )
