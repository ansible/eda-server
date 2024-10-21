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
from datetime import datetime, timezone

import django_rq
import rq

from aap_eda.analytics import collector
from aap_eda.conf import application_settings
from aap_eda.core import tasking

logger = logging.getLogger(__name__)


ANALYTICS_SCHEDULE_JOB_ID = "gather_analytics"
ANALYTICS_JOB_ID = "job_gather_analytics"
ANALYTICS_TASKS_QUEUE = "default"


@tasking.redis_connect_retry()
def schedule_gather_analytics() -> None:
    scheduler = django_rq.get_scheduler()
    func = "aap_eda.tasks.analytics.gather_analytics"
    scheduled_time = datetime.now(timezone.utc)
    interval = application_settings.AUTOMATION_ANALYTICS_GATHER_INTERVAL
    logger.info(
        f"Adding periodic job {ANALYTICS_SCHEDULE_JOB_ID} "
        f"to run every {interval} seconds"
    )
    scheduler.schedule(
        scheduled_time=scheduled_time,
        func=func,
        interval=interval,
        id=ANALYTICS_SCHEDULE_JOB_ID,
    )


@tasking.redis_connect_retry()
def reschedule_gather_analytics(new_interval: int, serializer=None) -> None:
    try:
        job = tasking.Job.fetch(
            ANALYTICS_SCHEDULE_JOB_ID, serializer=serializer
        )
    except rq.exceptions.NoSuchJobError:
        logger.warning(f"Job {ANALYTICS_SCHEDULE_JOB_ID} does not exist")
        return
    job.meta["interval"] = new_interval
    job.save()
    logger.info(
        f"Reconfigure periodic job {ANALYTICS_SCHEDULE_JOB_ID} with "
        f"new interval {new_interval} seconds"
    )


def gather_analytics(queue_name: str = ANALYTICS_TASKS_QUEUE) -> None:
    logger.info("Queue EDA analytics")
    tasking.unique_enqueue(queue_name, ANALYTICS_JOB_ID, _gather_analytics)


def _gather_analytics() -> None:
    if not application_settings.INSIGHTS_TRACKING_STATE:
        logger.info("INSIGHTS_TRACKING_STATE is not enabled")
        return
    logger.info("Collecting EDA analytics")
    tgzfiles = collector.gather(logger=logger)
    if not tgzfiles:
        logger.info("No analytics collected")
        return
    logger.info("Analytics collection is done")
