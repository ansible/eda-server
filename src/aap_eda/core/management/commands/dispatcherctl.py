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

"""Enhanced dispatcherctl command for worker management and debugging."""

import inspect
import logging
from typing import Any

import yaml
from dispatcherd import run_service as run_dispatcherd_service
from dispatcherd.config import setup as dispatcherd_setup
from dispatcherd.factories import get_control_from_settings
from dispatcherd.service import control_tasks
from django.conf import settings
from django.core.management.base import (
    BaseCommand,
    CommandError,
    CommandParser,
)

from aap_eda import utils
from aap_eda.utils.logging import startup_logging

logger = logging.getLogger(__name__)


# Output format (simplified to match AWX approach)
DEFAULT_OUTPUT_FORMAT = "yaml"


def format_output_yaml(data: Any) -> str:
    """Format command output as YAML (simplified from AWX approach).

    Args:
        data: Data to format

    Returns:
        YAML formatted string
    """
    return yaml.dump(data, default_flow_style=False)


class Command(BaseCommand):
    """Enhanced dispatcherctl command for worker management and debugging."""

    help = "Manage dispatcherd workers and debug their status"

    def __init__(self, *args, **kwargs):
        """Initialize command and perform startup logging."""
        super().__init__(*args, **kwargs)
        # Perform startup logging when command is instantiated
        startup_logging(logger)

    def add_arguments(self, parser: CommandParser) -> None:
        """Add command line arguments using dispatcherd.cli infrastructure."""
        parser.description = (
            "Run dispatcherd control commands using eda-manage."
        )

        subparsers = parser.add_subparsers(dest="command", metavar="command")
        subparsers.required = True

        # Activate subcommand (EDA-specific)
        activate_parser = subparsers.add_parser(
            "activate",
            help="Launch dispatcherd worker service",
        )
        activate_parser.add_argument(
            "--worker-type",
            required=True,
            choices=["ActivationWorker", "DefaultWorker"],
            help="Worker type: ActivationWorker or DefaultWorker",
        )

        # Add debug commands dynamically
        for command in control_tasks.__all__:
            func = getattr(control_tasks, command, None)
            doc = inspect.getdoc(func) or ""
            summary = doc.splitlines()[0] if doc else None
            command_parser = subparsers.add_parser(
                command,
                help=summary,
                description=doc,
            )

            # Add basic debug command arguments (simplified version)
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

    def handle_worker_subcommand(self, **options) -> None:
        """Handle worker launching functionality (enhanced existing code).

        Args:
            **options: Command options
        """
        worker_type = options.get("worker_type")
        verbosity = options.get("verbosity", 1)

        # Display startup information based on verbosity
        if verbosity >= 1:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting {worker_type} with dispatcherd..."
                )
            )

        try:
            if worker_type == "ActivationWorker":
                # ActivationWorker requires dynamic queue name configuration.
                # The queue name must be sanitized to prevent SQL injection
                # attacks and ensure PostgreSQL identifier compliance before
                # being used in pg_notify channels. PostgreSQL identifiers have
                # specific rules: they must be valid SQL identifiers,
                # alphanumeric with underscores, and properly quoted if they
                # contain special characters. We merge the sanitized channel
                # into the default settings after base settings are loaded to
                # ensure the queue name is safe for use.
                dispatcher_worker_settings = {
                    **settings.DISPATCHERD_DEFAULT_SETTINGS,
                    "brokers": {
                        "pg_notify": {
                            **settings.DISPATCHERD_DEFAULT_SETTINGS["brokers"][
                                "pg_notify"
                            ],
                            "channels": [
                                utils.sanitize_postgres_identifier(
                                    settings.RULEBOOK_QUEUE_NAME,
                                )
                            ],
                        },
                    },
                }
                dispatcherd_setup(dispatcher_worker_settings)

            elif worker_type == "DefaultWorker":
                dispatcherd_setup(settings.DISPATCHERD_DEFAULT_WORKER_SETTINGS)

            if verbosity >= 2:
                self.stdout.write(
                    "Worker configuration completed successfully."
                )

            logger.info(f"Starting {worker_type} with dispatcherd.")
            run_dispatcherd_service()

        except KeyboardInterrupt:
            if verbosity >= 1:
                self.stdout.write(
                    self.style.WARNING("Worker shutdown requested by user.")
                )
            logger.info(f"{worker_type} shutdown requested.")

        except Exception as e:
            error_msg = f"Failed to start {worker_type}: {e}"
            self.stderr.write(self.style.ERROR(error_msg))
            logger.error(error_msg, exc_info=True)
            raise SystemExit(1)

        if verbosity >= 1:
            self.stdout.write(
                self.style.SUCCESS(f"{worker_type} stopped gracefully.")
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

            formatted_output = format_output_yaml(result)
            self.stdout.write(formatted_output)

        except Exception as e:
            # Simplified error handling (following AWX approach)
            logger.error(
                f"Unexpected dispatcherctl debug command error: {e}",
                exc_info=True,
            )
            raise CommandError(f"Command failed: {e}")

    def handle(self, *args, **options) -> None:
        """Handle dispatcherctl command routing.

        Args:
            *args: Command arguments
            **options: Command options
        """
        command = options.get("command")

        if command == "activate":
            self.handle_worker_subcommand(**options)
        elif command in control_tasks.__all__:
            # Remove command from options to avoid duplicate parameter
            debug_options = {
                k: v for k, v in options.items() if k != "command"
            }
            self.handle_debug_subcommand(command, **debug_options)
        else:
            raise CommandError(f"Unknown subcommand: {command}")
