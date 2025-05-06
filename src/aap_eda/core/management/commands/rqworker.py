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

from dispatcherd import run_service
from dispatcherd.config import setup as dispatcherd_setup
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django_rq.management.commands import rqworker

from aap_eda.settings import features


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
            if "worker_class" not in options:
                self.style.ERROR("Missing required argument: --worker-class")
                raise SystemExit(1)

            # Use rqworker expected args to determine worker type
            if "ActivationWorker" in options["worker_class"]:
                worker_settings = settings.DISPATCHERD_DEFAULT_SETTINGS.copy()
                worker_settings["brokers"]["pg_notify"]["channels"] = [
                    settings.RULEBOOK_QUEUE_NAME.replace("-", "_")
                ]
                dispatcherd_setup(worker_settings)

            elif "DefaultWorker" in options["worker_class"]:
                worker_settings = settings.DISPATCHERD_DEFAULT_SETTINGS.copy()
                worker_settings["producers"] = {
                    "ScheduledProducer": {
                        "task_schedule": settings.DISPATCHERD_SCHEDULE_TASKS,
                    },
                    "OnStartProducer": {
                        "task_list": settings.DISPATCHERD_STARTUP_TASKS,
                    },
                }
                dispatcherd_setup(worker_settings)
            else:
                self.style.ERROR(
                    "Invalid worker class. "
                    "Please use either ActivationWorker or DefaultWorker."
                )
                raise SystemExit(1)

            run_service()

        # run rqworker command if dispatcherd is not enabled
        return rqworker.Command.handle(self, *args, **options)
