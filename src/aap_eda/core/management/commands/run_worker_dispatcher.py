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

import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from dispatcher import run_service
from dispatcher.config import settings, setup

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the worker dispatcher."

    # # TODO: stuff to support this isn't in yet
    # def add_arguments(self, parser):
    #     parser.add_argument(
    #       '--status', dest='status', action='store_true',
    # help='print the internal state of any running dispatchers')

    def handle(self, *args, **options):
        original_config = settings.serialize()
        new_config = original_config.copy()
        new_config['brokers']['pg_notify']['channels'] = ['eda_workers']
        new_config['producers'] = {
            "ScheduledProducer": {"task_schedule": settings.CELERYBEAT_SCHEDULE},
        }
        setup(new_config)

        run_service()
