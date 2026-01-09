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

"""Command for running dispatcherd worker service."""

import logging

from dispatcherd import run_service as run_dispatcherd_service
from dispatcherd.config import setup as dispatcherd_setup
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from aap_eda import utils
from aap_eda.utils.logging import startup_logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Command for running dispatcherd worker service."""

    help = "Run dispatcherd worker service"

    def __init__(self, *args, **kwargs):
        """Initialize command and perform startup logging."""
        super().__init__(*args, **kwargs)
        # Perform startup logging when command is instantiated
        startup_logging(logger)

    def add_arguments(self, parser: CommandParser) -> None:
        """Add command line arguments."""
        parser.add_argument(
            "--worker-class",
            required=True,
            choices=["ActivationWorker", "DefaultWorker"],
            help="Type of worker to run (ActivationWorker or DefaultWorker)",
        )

    def handle(self, *args, **options) -> None:
        """Handle dispatcherd service."""
        worker_class = options.get("worker_class")
        verbosity = options.get("verbosity", 1)

        try:
            if worker_class == "ActivationWorker":
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

            elif worker_class == "DefaultWorker":
                dispatcherd_setup(settings.DISPATCHERD_DEFAULT_WORKER_SETTINGS)

            # Output startup message with verbosity control
            if verbosity >= 1:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Starting {worker_class} with dispatcherd."
                    )
                )

            if verbosity >= 2:
                self.stdout.write(
                    self.style.SUCCESS(f"Worker type: {worker_class}")
                )

            logger.info(f"Starting {worker_class} with dispatcherd.")
            run_dispatcherd_service()

        except KeyboardInterrupt:
            shutdown_msg = f"{worker_class} shutdown requested."
            self.stdout.write(self.style.WARNING(shutdown_msg))
            logger.info(shutdown_msg)

        except Exception as e:
            error_msg = f"Failed to start {worker_class}: {e}"
            self.stderr.write(self.style.ERROR(error_msg))
            logger.error(error_msg, exc_info=True)
            raise SystemExit(1)
