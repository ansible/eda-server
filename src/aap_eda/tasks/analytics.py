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

from flags.state import flag_enabled

from aap_eda.analytics import collector, utils
from aap_eda.core import tasking

logger = logging.getLogger(__name__)


ANALYTICS_SCHEDULE_JOB_ID = "gather_analytics"
ANALYTICS_JOB_ID = "job_gather_analytics"
ANALYTICS_TASKS_QUEUE = "default"


def schedule_gather_analytics(queue_name: str = ANALYTICS_TASKS_QUEUE) -> None:
    if not flag_enabled("FEATURE_EDA_ANALYTICS_ENABLED"):
        return
    interval = utils.get_analytics_interval()
    logger.info(f"Schedule analytics to run in {interval} seconds")
    tasking.enqueue_delay(
        queue_name,
        ANALYTICS_SCHEDULE_JOB_ID,
        interval,
        auto_gather_analytics,
    )


def auto_gather_analytics(queue_name: str = ANALYTICS_TASKS_QUEUE) -> None:
    gather_analytics(queue_name)
    schedule_gather_analytics()


def gather_analytics(queue_name: str = ANALYTICS_TASKS_QUEUE) -> None:
    logger.info("Queue EDA analytics")
    tasking.unique_enqueue(queue_name, ANALYTICS_JOB_ID, _gather_analytics)


def _gather_analytics() -> None:
    if not utils.get_insights_tracking_state():
        logger.info("INSIGHTS_TRACKING_STATE is not enabled")
        return
    logger.info("Collecting EDA analytics")
    tgzfiles = collector.gather(logger=logger)
    if not tgzfiles:
        logger.info("No analytics collected")
        return
    logger.info("Analytics collection is done")
