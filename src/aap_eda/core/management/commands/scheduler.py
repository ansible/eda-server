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
import re
from datetime import datetime
from time import sleep

import django_rq
import redis
from ansible_base.lib.redis.client import DABRedisCluster
from django.conf import settings
from django_rq.management.commands import rqscheduler
from rq_scheduler import Scheduler

logger = logging.getLogger(__name__)


RQ_STARTUP_JOBS = getattr(settings, "RQ_STARTUP_JOBS", None)
RQ_PERIODIC_JOBS = getattr(settings, "RQ_PERIODIC_JOBS", None)
RQ_CRON_JOBS = getattr(settings, "RQ_CRON_JOBS", None)


def delete_scheduled_jobs(scheduler: Scheduler):
    """Cancel any existing jobs in the scheduler when the app starts up."""
    for job in scheduler.get_jobs():
        logging.info("Deleting scheduled job: %s", job)
        job.delete()


def add_startup_jobs(scheduler: Scheduler) -> None:
    if not RQ_STARTUP_JOBS:
        logger.info("No scheduled jobs. Skipping.")
        return

    for entry in RQ_STARTUP_JOBS:
        logger.info('Adding startup job "%s"', entry["func"])
        scheduled_time = entry.pop("scheduled_time", None)
        if scheduled_time is None:
            scheduled_time = datetime.utcnow()
        scheduler.enqueue_at(
            scheduled_time=scheduled_time,
            **entry,
        )


def add_periodic_jobs(scheduler: Scheduler) -> None:
    if not RQ_PERIODIC_JOBS:
        logger.info("No periodic jobs. Skipping.")
        return

    for entry in RQ_PERIODIC_JOBS:
        logger.info('Adding periodic job "%s"', entry["func"])
        scheduled_time = entry.pop("scheduled_time", None)
        if scheduled_time is None:
            scheduled_time = datetime.utcnow()
        scheduler.schedule(
            scheduled_time=scheduled_time,
            **entry,
        )


def add_cron_jobs(scheduler: Scheduler) -> None:
    """Schedule cron jobs."""
    if not RQ_CRON_JOBS:
        logger.info("No cron jobs. Skipping.")
        return

    for entry in RQ_CRON_JOBS:
        logger.info('Adding cron job "%s"', entry["func"])
        scheduler.cron(**entry)


class Command(rqscheduler.Command):
    help = "Runs RQ scheduler with configured jobs."

    def handle(self, *args, **options) -> None:
        # interval can be set through the command line
        # but we want to manage it through settings
        options["interval"] = settings.RQ_SCHEDULER_JOB_INTERVAL

        logging.info("Initializing scheduler")
        scheduler = django_rq.get_scheduler()
        delete_scheduled_jobs(scheduler)
        add_startup_jobs(scheduler)
        add_periodic_jobs(scheduler)
        add_cron_jobs(scheduler)
        # We are going to start our own loop here to catch exceptions which
        # might be coming from a redis cluster and retrying things.
        while True:
            try:
                super().handle(*args, **options)
            except (
                redis.exceptions.TimeoutError,
                redis.exceptions.ClusterDownError,
                redis.exceptions.ConnectionError,
            ) as e:
                # If we got one of these exceptions but are not on a Cluster go
                # ahead and raise it normally.
                if not isinstance(scheduler.connection, DABRedisCluster):
                    raise

                # There are a lot of different exceptions that inherit from
                # ConnectionError.  So we need to make sure if we got that its
                # an actual ConnectionError. If not, go ahead and raise it.
                # Note:  ClusterDownError and TimeoutError are not subclasses
                #        of ConnectionError.
                if (
                    issubclass(type(e), redis.exceptions.ConnectionError)
                    and type(e) is not redis.exceptions.ConnectionError
                ):
                    raise

                downed_node_ip = re.findall(r'[0-9]+(?:\.[0-9]+){3}:[0-9]+', str(e))

                # If we got a cluster issue we will loop here until we can ping
                # the server again.
                max_backoff = 60
                current_backoff = 1
                while True:
                    if current_backoff > max_backoff:
                        # Maybe we just got a network glitch and are waiting for
                        # a cluster member to fail when its not going to. At this
                        # point we've waited for 60 secs so lets go ahead and let
                        # the scheduler try and restart                          
                        logger.error(
                            "Connection to redis is still down "
                            "going to attempt to restart scheduler"
                        )
                        break

                    backoff = min(current_backoff, max_backoff)
                    logger.error(
                        f"Connection to redis cluster failed. Attempting to "
                        f"reconnect in {backoff}"
                    )
                    sleep(backoff)
                    current_backoff = 2 * current_backoff
                    try:
                        if downed_node_ip:
                            cluster_nodes = scheduler.connection.cluster_nodes()
                            for ip in downed_node_ip:
                                if 'fail' not in cluster_nodes[ip]['flags']:
                                    raise Exception("Failed node is not yet in a failed state")
                        else:
                            scheduler.connection.ping()
                        break
                    # We could tighten this exception up
                    except Exception:
                        pass
