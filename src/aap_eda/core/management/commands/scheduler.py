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
"""Initialize scheduled tasks and run scheduler.

When executed this management command will delete existing scheduled
tasks, add new tasks according to settings and execute RQ scheduler.

Jobs are configured in three lists:
    * Startup jobs (``RQ_STARTUP_JOBS``) – one-time jobs executed at
        scheduler startup time.
    * Periodic jobs (``RQ_PERIODIC_JOBS``) – jobs executed repeatedly
        with fixed time interval.
    * Cron jobs (``RQ_CRON_JOBS``) – jobs, defined by a crontab string.

Startup jobs.

Example::

  RQ_STARTUP_JOBS = [
      {
          "func": "package.module.funcname",
          "scheduled_time": datetime(2020, 1, 1),
      }
  ]


Periodic jobs.

Example::

    RQ_PERIODIC_JOBS = [
        {
            # Function to be queued
            "func": "package.module.funcname",
            # Time before the function is called again (in seconds).
            "interval": 60,
            # Time for first execution, in UTC timezone
            ...
        }
    ]

For a complete list of parameters refer to the
https://github.com/rq/rq-scheduler/blob/master/README.rst

Cron jobs.

Example::

    RQ_CRON_JOBS = [
        {
            # Function to be queued
            "func": "package.module.funcname",
            # A cron string
            "cron_string": "0 0 * * 0",
        }
    ]

For a complete list of parameters refer to the
https://github.com/rq/rq-scheduler/blob/master/README.rst
"""
import logging
import signal
import time
import typing
from datetime import datetime

import django_rq
import rq_scheduler
from django.conf import settings
from django_rq.management.commands import rqscheduler

from aap_eda.core import tasking
from aap_eda.core.exceptions import GracefulExit
from aap_eda.settings import features
from aap_eda.utils.logging import startup_logging

logger = logging.getLogger(__name__)


RQ_STARTUP_JOBS = getattr(settings, "RQ_STARTUP_JOBS", None)
RQ_PERIODIC_JOBS = getattr(settings, "RQ_PERIODIC_JOBS", None)
RQ_CRON_JOBS = getattr(settings, "RQ_CRON_JOBS", None)


@tasking.redis_connect_retry()
def delete_scheduled_jobs(scheduler: rq_scheduler.Scheduler) -> None:
    """Cancel any existing jobs in the scheduler when the app starts up."""
    for job in scheduler.get_jobs():
        logger.info("Deleting scheduled job: %s", job)
        job.delete()


def add_startup_jobs(scheduler: rq_scheduler.Scheduler) -> None:
    if not RQ_STARTUP_JOBS:
        logger.info("No scheduled jobs. Skipping.")
        return

    @tasking.redis_connect_retry()
    def _add_startup_job(
        scheduler: rq_scheduler.Scheduler,
        entry: dict[str, typing.Any],
    ) -> None:
        logger.info('Adding startup job "%s"', entry["func"])
        scheduled_time = entry.pop("scheduled_time", None)
        if scheduled_time is None:
            scheduled_time = datetime.utcnow()
        scheduler.enqueue_at(
            scheduled_time=scheduled_time,
            **entry,
        )

    for entry in RQ_STARTUP_JOBS:
        _add_startup_job(scheduler, entry)


def add_periodic_jobs(scheduler: rq_scheduler.Scheduler) -> None:
    if not RQ_PERIODIC_JOBS:
        logger.info("No periodic jobs. Skipping.")
        return

    @tasking.redis_connect_retry()
    def _add_periodic_job(
        scheduler: rq_scheduler.Scheduler,
        entry: dict[str, typing.Any],
    ) -> None:
        logger.info('Adding periodic job "%s"', entry["func"])
        scheduled_time = entry.pop("scheduled_time", None)
        if scheduled_time is None:
            scheduled_time = datetime.utcnow()
        scheduler.schedule(
            scheduled_time=scheduled_time,
            **entry,
        )

    for entry in RQ_PERIODIC_JOBS:
        _add_periodic_job(scheduler, entry)


def add_cron_jobs(scheduler: rq_scheduler.Scheduler) -> None:
    """Schedule cron jobs."""
    if not RQ_CRON_JOBS:
        logger.info("No cron jobs. Skipping.")
        return

    @tasking.redis_connect_retry()
    def _add_cron_job(
        scheduler: rq_scheduler.Scheduler,
        entry: dict[str, typing.Any],
    ) -> None:
        logger.info('Adding cron job "%s"', entry["func"])
        scheduler.cron(**entry)

    for entry in RQ_CRON_JOBS:
        _add_cron_job(scheduler, entry)


class Command(rqscheduler.Command):
    help = "Runs RQ scheduler with configured jobs."

    def handle(self, *args, **options) -> None:
        if features.DISPATCHERD:
            self.stdout.write(
                self.style.WARNING(
                    f"{settings.DISPATCHERD_FEATURE_FLAG_NAME} flag "
                    "is enabled. This command is not required in this setup. "
                    "You may update your deployment configuration to omit "
                    "this process. \nRunning in background (noop mode)...",
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
                self.stdout.write(self.style.NOTICE("Exiting noop mode."))
                return

        # interval can be set through the command line
        # but we want to manage it through settings
        options["interval"] = settings.RQ_SCHEDULER_JOB_INTERVAL

        startup_logging(logger)
        logger.info("Initializing scheduler")

        scheduler = django_rq.get_scheduler()
        delete_scheduled_jobs(scheduler)
        add_startup_jobs(scheduler)
        add_periodic_jobs(scheduler)
        add_cron_jobs(scheduler)
        super().handle(*args, **options)

    handle = tasking.redis_connect_retry()(handle)
