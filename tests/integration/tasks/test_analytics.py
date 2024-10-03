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

from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest
from rq.serializers import DefaultSerializer

from aap_eda.conf import application_settings, settings_registry
from aap_eda.core.tasking import DefaultWorker, Job, Queue, Scheduler
from aap_eda.tasks import analytics


@pytest.fixture(autouse=True)
def register() -> None:
    settings_registry.persist_registry_data()
    return None


@pytest.mark.django_db
def test_gather_analytics(default_queue: Queue):
    with mock.patch("aap_eda.analytics.collector.gather") as mock_method:
        # purposely fail the gather() method in order to assert it gets called
        mock_method.side_effect = AssertionError("gather called")
        application_settings.INSIGHTS_TRACKING_STATE = True
        default_queue.enqueue(analytics.gather_analytics, default_queue.name)

        worker = DefaultWorker(
            [default_queue], connection=default_queue.connection
        )
        worker.work(burst=True)

        job = Job.fetch(analytics.ANALYTICS_JOB_ID, default_queue.connection)
        result = job.latest_result()
        assert "AssertionError: gather called" in result.exc_string
        assert result.type == result.Type.FAILED


@pytest.mark.django_db
def test_schedule_and_reschedule(default_queue: Queue):
    scheduler = Scheduler(
        queue_name=default_queue.name, connection=default_queue.connection
    )
    with mock.patch(
        "aap_eda.tasks.analytics.django_rq.get_scheduler",
        return_value=scheduler,
    ):
        analytics.schedule_gather_analytics()
        scheduler.run(burst=True)
        job = Job.fetch(
            analytics.ANALYTICS_SCHEDULE_JOB_ID,
            default_queue.connection,
            serializer=DefaultSerializer,
        )
        # the first job scheduled to run immediately
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        assert abs(job.enqueued_at - now) < timedelta(seconds=1)
        assert (
            job.meta["interval"]
            == application_settings.AUTOMATION_ANALYTICS_GATHER_INTERVAL
        )

        analytics.reschedule_gather_analytics(
            500, serializer=DefaultSerializer
        )
        job.refresh()
        assert job.meta["interval"] == 500


@pytest.mark.django_db
def test_reschedule_without_scheduler():
    # should not raise any error
    analytics.reschedule_gather_analytics(500)
