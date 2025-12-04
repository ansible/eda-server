#  Copyright 2023 Red Hat, Inc.
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
"""Legacy scheduler command (no longer required).

This command is no longer required as dispatcherd handles all task scheduling
internally through DISPATCHERD_STARTUP_TASKS and DISPATCHERD_SCHEDULE_TASKS
settings. The command is kept for compatibility but runs in no-op mode.

Task configuration has moved to:
    * DISPATCHERD_STARTUP_TASKS - one-time tasks executed at startup
    * DISPATCHERD_SCHEDULE_TASKS - recurring tasks with intervals
"""
import logging
import signal
import time

from django.core.management.base import BaseCommand

from aap_eda.core.exceptions import GracefulExit
from aap_eda.utils.logging import startup_logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Legacy scheduler command (no longer required with dispatcherd)."

    def handle(self, *args, **options) -> None:
        startup_logging(logger)
        self.stdout.write(
            self.style.WARNING(
                "This scheduler command is no longer required with "
                "dispatcherd. "
                "Task scheduling is handled automatically through "
                "DISPATCHERD_STARTUP_TASKS and DISPATCHERD_SCHEDULE_TASKS "
                "settings. You may update your deployment configuration to "
                "omit this process. \nRunning in no-op mode...",
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
            self.stdout.write(self.style.NOTICE("Exiting no-op mode."))
            return
