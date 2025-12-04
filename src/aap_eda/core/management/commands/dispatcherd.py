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

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Command for running dispatcherd worker service."""

    help = "Run dispatcherd worker service"

    def add_arguments(self, parser: CommandParser) -> None:
        """Add command line arguments."""
        parser.add_argument(
            "--worker-class",
            required=True,
            choices=["ActivationWorker", "DefaultWorker"],
            help="Type of worker to run (ActivationWorker or DefaultWorker)",
        )

        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="INFO",
            help="Logging level (default: INFO)",
        )

    def handle(self, *args, **options) -> None:
        """Handle dispatcherd service."""
        worker_class = options.get("worker_class")
        log_level = options.get("log_level", "INFO")
        verbosity = options.get("verbosity", 1)

        # Set logging level
        logging.getLogger().setLevel(getattr(logging, log_level))

        # Display startup information based on verbosity
        if verbosity >= 1:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting {worker_class} with dispatcherd..."
                )
            )

        try:
            if worker_class == "ActivationWorker":
                # dispatcherd worker settings can not be initialized as setting
                # because the queue name sanitization must happen
                # after the settings are loaded.
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

            if verbosity >= 2:
                self.stdout.write(
                    "Worker configuration completed successfully."
                )

            logger.info(f"Starting {worker_class} with dispatcherd.")
            run_dispatcherd_service()

        except KeyboardInterrupt:
            if verbosity >= 1:
                self.stdout.write(
                    self.style.WARNING("Worker shutdown requested by user.")
                )
            logger.info(f"{worker_class} shutdown requested.")

        except Exception as e:
            error_msg = f"Failed to start {worker_class}: {e}"
            self.stderr.write(self.style.ERROR(error_msg))
            logger.error(error_msg, exc_info=True)
            raise SystemExit(1)

        if verbosity >= 1:
            self.stdout.write(
                self.style.SUCCESS(f"{worker_class} stopped gracefully.")
            )
