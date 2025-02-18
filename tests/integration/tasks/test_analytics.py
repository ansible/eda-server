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


import time
from unittest import mock

import pytest
from rq.serializers import DefaultSerializer

from aap_eda.core.tasking import DefaultWorker, Job, Queue, Scheduler
from aap_eda.tasks import analytics


@pytest.fixture
def analytics_settings():
    """Mock application settings with proper attribute access."""

    class Settings:
        INSIGHTS_TRACKING_STATE = True
        AUTOMATION_ANALYTICS_LAST_GATHER = None
        AUTOMATION_ANALYTICS_LAST_ENTRIES = '{"key": "value"}'
        AUTOMATION_ANALYTICS_GATHER_INTERVAL = 2

    return Settings()


def test_gather_analytics(analytics_settings, default_queue: Queue):
    with mock.patch("aap_eda.analytics.collector.gather") as mock_method:
        with mock.patch(
            "aap_eda.tasks.analytics.application_settings",
            new=analytics_settings,
        ):
            # purposely fail the gather() method in order to assert it
            # gets called
            mock_method.side_effect = AssertionError("gather called")

            default_queue.enqueue(
                analytics.gather_analytics, default_queue.name
            )

            worker = DefaultWorker(
                [default_queue], connection=default_queue.connection
            )
            worker.work(burst=True)

            job = Job.fetch(
                analytics.ANALYTICS_JOB_ID, default_queue.connection
            )
            result = job.latest_result()
            assert "AssertionError: gather called" in result.exc_string
            assert result.type == result.Type.FAILED


def test_auto_gather_analytics():
    with mock.patch("aap_eda.tasks.analytics.gather_analytics") as mock_gather:
        with mock.patch(
            "aap_eda.tasks.analytics.schedule_gather_analytics"
        ) as mock_schdule:
            analytics.auto_gather_analytics()
            mock_gather.assert_called_once()
            mock_schdule.assert_called_once()


def test_schedule_gather_analytics(analytics_settings, default_queue: Queue):
    scheduler = Scheduler(
        queue_name=default_queue.name, connection=default_queue.connection
    )
    with mock.patch(
        "aap_eda.core.tasking.django_rq.get_scheduler",
        return_value=scheduler,
    ):
        with mock.patch(
            "aap_eda.tasks.analytics.application_settings",
            new=analytics_settings,
        ):
            analytics.schedule_gather_analytics(default_queue.name)
            scheduler.run(burst=True)
            job = Job.fetch(
                analytics.ANALYTICS_SCHEDULE_JOB_ID,
                default_queue.connection,
                serializer=DefaultSerializer,
            )
            assert job.enqueued_at is None
            assert (
                job.func_name
                == "aap_eda.tasks.analytics.auto_gather_analytics"
            )

            time.sleep(analytics_settings.AUTOMATION_ANALYTICS_GATHER_INTERVAL)
            scheduler.run(burst=True)
            job.refresh()
            assert job.enqueued_at is not None
