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

import argparse
import inspect
import logging

import yaml
from dispatcherd.cli import (
    CONTROL_ARG_SCHEMAS,
    _base_cli_parent,
    _build_command_data_from_args,
    _control_common_parent,
    _register_control_arguments,
)
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
            "Run dispatcherd control commands using aap-eda-manage."
        )

        # Use dispatcherd's CLI parents for consistent argument structure
        base_parent = _base_cli_parent()
        control_parent = _control_common_parent()
        parser._add_container_actions(base_parent)
        parser._add_container_actions(control_parent)

        subparsers = parser.add_subparsers(dest="command", metavar="command")
        subparsers.required = True
        shared_parents = [base_parent, control_parent]

        # Dynamically add commands using dispatcherd's schemas
        for command in control_tasks.__all__:
            func = getattr(control_tasks, command, None)
            doc = inspect.getdoc(func) or ""
            summary = doc.splitlines()[0] if doc else None
            command_parser = subparsers.add_parser(
                command,
                help=summary,
                description=doc,
                parents=shared_parents,
            )
            # Use dispatcherd's own argument registration
            _register_control_arguments(
                command_parser, CONTROL_ARG_SCHEMAS.get(command)
            )

    def handle(self, *args, **options) -> None:
        """Handle dispatcherctl debug command routing."""
        command = options.get("command")
        if not command:
            raise CommandError("No dispatcher control command specified")

        # Remove Django-specific options
        for django_opt in (
            "verbosity",
            "traceback",
            "no_color",
            "force_color",
            "skip_checks",
        ):
            options.pop(django_opt, None)

        expected_replies = options.pop("expected_replies", 1)

        try:
            # Setup dispatcherd configuration using Django settings
            logger.info(
                "Using config generated from "
                "settings.DISPATCHERD_DEFAULT_SETTINGS"
            )
            dispatcherd_setup(settings.DISPATCHERD_DEFAULT_SETTINGS)

            # Use dispatcherd's data builder
            schema_namespace = argparse.Namespace(**options)
            data = _build_command_data_from_args(schema_namespace, command)

            # Execute command using dispatcherd's control interface
            ctl = get_control_from_settings()
            returned = ctl.control_with_reply(
                command, data=data, expected_replies=expected_replies
            )

            # Check reply count FIRST
            if len(returned) < expected_replies:
                logger.error(
                    f"Obtained only {len(returned)} of {expected_replies}"
                )
                raise CommandError(
                    "dispatcherctl returned fewer replies than expected"
                )

            # Output results only after validation
            self.stdout.write(yaml.dump(returned, default_flow_style=False))

        except KeyboardInterrupt:
            logger.info(
                "Received interrupt signal, shutting down dispatcherctl"
            )
            raise CommandError("Command interrupted by user")
        except Exception as e:
            error_msg = f"Failed to execute {command}: {e}"
            logger.error(error_msg, exc_info=True)
            raise CommandError(error_msg)
