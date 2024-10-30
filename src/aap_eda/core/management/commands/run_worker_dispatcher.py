#  Copyright 2024 Red Hat, Inc.
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

import asyncio
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from dispatcher.main import DispatcherMain

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the worker dispatcher."

    # # TODO: stuff to support this isn't in yet
    # def add_arguments(self, parser):
    #     parser.add_argument('--status', dest='status', action='store_true', help='print the internal state of any running dispatchers')

    def handle(self, *args, **options):
        # NOTE: using a channel named literally "default" will give a postgres SynaxError.
        # It seems to be some kind of reserved variable name in postgres.
        dispatcher_config = {
            "producers": {
                "brokers": {
                    "pg_notify": {"conninfo": settings.PG_NOTIFY_DSN_SERVER},
                    "channels": ["eda_workers"],
                },
                "scheduled": settings.CELERYBEAT_SCHEDULE,
            },
            "pool": {"max_workers": 4},
        }

        loop = asyncio.get_event_loop()
        dispatcher = DispatcherMain(dispatcher_config)
        try:
            loop.run_until_complete(dispatcher.main())
        except KeyboardInterrupt:
            logger.info("run_worker_dispatch entry point leaving")
        finally:
            loop.close()
