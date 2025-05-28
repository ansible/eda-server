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

"""Wrapper for rqworker command."""

import logging

from dispatcherd import run_service as run_dispatcherd_service
from dispatcherd.config import setup as dispatcherd_setup
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django_rq.management.commands import rqworker

from aap_eda.settings import features

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Wrapper for rqworker command.

    Switches between rqworker and dispatcherd commands based on
    the dispatcherd feature flag.
    """

    args = rqworker.Command.args

    def add_arguments(self, parser: CommandParser) -> None:
        return rqworker.Command.add_arguments(self, parser)

    def handle(self, *args, **options) -> None:
        if features.DISPATCHERD:
            return self._handle_dispatcherd(*args, **options)

        # run rqworker command if dispatcherd is not enabled
        logger.info("Starting worker with rqworker.")
        return rqworker.Command.handle(self, *args, **options)

    def _handle_dispatcherd(self, *args, **options) -> None:
        """Handle dispatcherd service."""
        if "worker_class" not in options:
            self.style.ERROR("Missing required argument: --worker-class")
            raise SystemExit(1)

        # Use rqworker expected args to determine worker type
        if "ActivationWorker" in options["worker_class"]:
            dispatcherd_setup(
                settings.DISPATCHERD_ACTIVATION_WORKER_SETTINGS,
            )

        elif "DefaultWorker" in options["worker_class"]:
            dispatcherd_setup(settings.DISPATCHERD_DEFAULT_WORKER_SETTINGS)
        else:
            self.style.ERROR(
                "Invalid worker class. "
                "Please use either ActivationWorker or DefaultWorker."
            )
            raise SystemExit(1)

        logger.info("Starting worker with dispatcherd.")
        run_dispatcherd_service()
        return None
