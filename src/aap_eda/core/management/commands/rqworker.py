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
"""Legacy rqworker command (replaced by dispatcherd).

This command has been replaced by the dispatcherd command as part of the
migration from Redis/RQ to PostgreSQL pg_notify for task processing.

The new dispatcherd command provides the same functionality with improved
reliability and reduced infrastructure dependencies.

Migration path:
    Old: python manage.py rqworker <queue_name>
    New: python manage.py dispatcherd --worker-class <WorkerClass>

Worker class mapping:
    * Default queue -> DefaultWorker
    * Activation queue -> ActivationWorker
"""
import logging
import signal
import time

from django.core.management.base import BaseCommand

from aap_eda.core.exceptions import GracefulExit
from aap_eda.utils.logging import startup_logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Legacy rqworker command (replaced by dispatcherd)."

    def add_arguments(self, parser):
        parser.add_argument(
            "queues",
            nargs="*",
            help=(
                "Queue names (legacy parameter, "
                "will be mapped to worker class)"
            ),
        )
        parser.add_argument(
            "--worker-class",
            help="Worker class to use (legacy parameter)",
        )

    def handle(self, *args, **options) -> None:
        startup_logging(logger)

        queues = options.get("queues", [])
        worker_class = options.get("worker_class")

        # Determine the appropriate dispatcherd command
        if queues:
            queue_name = queues[0]  # Use first queue for mapping
            if queue_name == "activation":
                suggested_command = (
                    "python manage.py dispatcherd "
                    "--worker-class ActivationWorker"
                )
            else:
                suggested_command = (
                    "python manage.py dispatcherd "
                    "--worker-class DefaultWorker"
                )
        elif worker_class:
            suggested_command = (
                f"python manage.py dispatcherd "
                f"--worker-class {worker_class}"
            )
        else:
            suggested_command = (
                "python manage.py dispatcherd --worker-class DefaultWorker"
            )

        self.stdout.write(
            self.style.WARNING(
                "The 'rqworker' command has been replaced by 'dispatcherd' as "
                "part of the migration from Redis/RQ to PostgreSQL "
                "pg_notify.\n\n"
                f"Please update your deployment to use:\n  "
                f"{suggested_command}\n\n"
                "Benefits of dispatcherd:\n"
                "  • Eliminates Redis dependency\n"
                "  • Improved task reliability with PostgreSQL ACID "
                "properties\n"
                "  • Better resource utilization\n"
                "  • Simplified deployment architecture\n\n"
                "Running in compatibility mode (no-op)..."
            ),
        )

        def handle_exit(signum, frame):
            raise GracefulExit()

        signal.signal(signal.SIGTERM, handle_exit)
        signal.signal(signal.SIGINT, handle_exit)

        try:
            while True:
                time.sleep(60)
        except GracefulExit:
            self.stdout.write(self.style.NOTICE("Exiting compatibility mode."))
            return
