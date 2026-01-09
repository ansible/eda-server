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

"""Dispatcherctl management command for debug tools."""

import logging

import yaml
from dispatcherd.config import setup as dispatcherd_setup
from dispatcherd.factories import get_control_from_settings
from dispatcherd.service import control_tasks
from django.conf import settings
from django.core.management.base import (
    BaseCommand,
    CommandError,
    CommandParser,
)

from aap_eda.utils.logging import startup_logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Dispatcherctl management command for debug tools."""

    help = "Dispatcherctl management command for debug tools"

    def __init__(self, *args, **kwargs):
        """Initialize command and perform startup logging."""
        super().__init__(*args, **kwargs)
        # Perform startup logging when command is instantiated
        startup_logging(logger)

    def add_arguments(self, parser: CommandParser) -> None:
        """Add command line arguments for debug commands."""
        parser.description = (
            "Dispatcherctl debug tools. For worker services, use "
            "'aap-eda-manage dispatcherd'."
        )

        subparsers = parser.add_subparsers(dest="command", metavar="command")
        subparsers.required = False

        # Dynamically add debug commands from dispatcherd
        for command in control_tasks.__all__:
            command_func = getattr(control_tasks, command)
            if hasattr(command_func, "__doc__") and command_func.__doc__:
                help_text = command_func.__doc__.strip()
            else:
                help_text = f"Run {command} debug command"

            command_parser = subparsers.add_parser(command, help=help_text)

            # Common arguments for all debug commands
            command_parser.add_argument(
                "--task",
                type=str,
                help="Task name to filter on.",
            )
            command_parser.add_argument(
                "--uuid",
                type=str,
                help="Task uuid to filter on.",
            )
            command_parser.add_argument(
                "--expected-replies",
                type=int,
                default=1,
                help="Expected number of replies.",
            )

            # Add set_log_level specific argument
            if command == "set_log_level":
                command_parser.add_argument(
                    "--log-level",
                    type=str,
                    required=True,
                    choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                    help="Python log level to set.",
                )

            # Add aio_tasks specific argument
            if command == "aio_tasks":
                command_parser.add_argument(
                    "--limit",
                    type=int,
                    default=1,
                    required=False,
                    help="Maximum number of async tasks to return.",
                )

    def handle_debug_subcommand(self, command: str, **options) -> None:
        """Handle debug commands.

        Args:
            command: Debug command to execute
            **options: Command options
        """
        expected_replies = options.get("expected_replies", 1)

        # Validate debug command (dynamic discovery)
        available_commands = control_tasks.__all__
        if command not in available_commands:
            raise CommandError(
                f"Invalid debug command '{command}'. "
                f"Must be one of: {', '.join(available_commands)}"
            )

        try:
            # Setup dispatcherd control interface
            dispatcherd_setup(settings.DISPATCHERD_DEFAULT_SETTINGS)
            ctl = get_control_from_settings()

            # Build command data (simplified version)
            data = {}
            for field in ("task", "uuid"):
                val = options.get(field)
                if val:
                    data[field] = val

            # Add log level for set_log_level command
            if command == "set_log_level":
                log_level = options.get("log_level")
                if not log_level:
                    raise CommandError(
                        f"--log-level is required for {command} command"
                    )
                data["level"] = log_level

            # Execute control command
            returned = ctl.control_with_reply(
                command=command,
                data=data,
                expected_replies=expected_replies,
            )

            # Check if we got enough replies (essential check from AWX)
            if len(returned) < expected_replies:
                logger.error(
                    f"Obtained only {len(returned)} of {expected_replies}"
                )
                raise CommandError(
                    "dispatcherctl returned fewer replies than expected"
                )

            # Format and output results
            if len(returned) == 1:
                # Single reply - output directly
                result = returned[0]
            else:
                # Multiple replies - create dict with reply indexes
                result = {
                    f"reply-{i}": reply for i, reply in enumerate(returned)
                }

            formatted_output = yaml.dump(result, default_flow_style=False)
            self.stdout.write(formatted_output)

        except Exception as e:
            # Simplified error handling (following AWX approach)
            logger.error(
                f"Unexpected dispatcherctl debug command error: {e}",
                exc_info=True,
            )
            raise CommandError(f"Command failed: {e}")

    def handle(self, *args, **options) -> None:
        """Handle dispatcherctl debug command routing.

        Args:
            *args: Command arguments
            **options: Command options
        """
        command = options.get("command")

        if command is None:
            # No subcommand provided - show available debug commands
            available_commands = ", ".join(control_tasks.__all__)
            self.stdout.write(
                self.style.SUCCESS(
                    "Dispatcherctl debug tools\n\n"
                    f"Available debug commands: {available_commands}\n\n"
                    "Note: Debug commands require a running dispatcher "
                    "service.\n"
                    "Start a dispatcher service first:\n"
                    "  aap-eda-manage dispatcherd --worker-class "
                    "<WorkerType>\n\n"
                    "Usage:\n"
                    f"  aap-eda-manage dispatcherctl <command>\n\n"
                    "For worker services, use:\n"
                    "  aap-eda-manage dispatcherd --worker-class "
                    "<WorkerType>\n"
                )
            )
            return

        # Check if the command is available in control_tasks
        if command in control_tasks.__all__:
            # Remove command from options to avoid duplicate parameter
            debug_options = {
                k: v for k, v in options.items() if k != "command"
            }
            self.handle_debug_subcommand(command, **debug_options)
        else:
            # Unknown command
            available_commands = ", ".join(control_tasks.__all__)
            self.stderr.write(
                self.style.ERROR(
                    f"Unknown debug command '{command}'.\n"
                    f"Available commands: {available_commands}\n"
                    "For worker services, use: aap-eda-manage dispatcherd "
                    "--worker-class <WorkerType>"
                )
            )
            raise CommandError(f"Unknown subcommand: {command}")
