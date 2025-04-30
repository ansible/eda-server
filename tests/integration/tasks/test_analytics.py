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


from unittest import mock

import pytest

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


def test_auto_gather_analytics():
    with mock.patch(
        "aap_eda.tasks.analytics.gather_analytics"
    ) as mock_gather, mock.patch(
        "aap_eda.tasks.analytics.schedule_gather_analytics"
    ) as mock_schdule:
        analytics.auto_gather_analytics()
        mock_gather.assert_called_once()
        mock_schdule.assert_called_once()


@pytest.mark.django_db
def test_schedule_gather_analytics_success():
    test_interval = 3600
    test_queue = "test_queue"

    with mock.patch(
        "aap_eda.tasks.analytics.utils.get_analytics_interval"
    ) as mock_interval, mock.patch(
        "aap_eda.tasks.analytics.tasking.enqueue_delay"
    ) as mock_enqueue, mock.patch(
        "aap_eda.tasks.analytics.logger.info"
    ) as mock_logger, mock.patch(
        "aap_eda.tasks.analytics.flag_enabled",
        return_value=True,
    ):
        mock_interval.return_value = test_interval

        analytics.schedule_gather_analytics(test_queue)

        mock_interval.assert_called_once()
        mock_logger.assert_called_once_with(
            f"Schedule analytics to run in {test_interval} seconds"
        )
        mock_enqueue.assert_called_once_with(
            test_queue,
            analytics.ANALYTICS_SCHEDULE_JOB_ID,
            test_interval,
            analytics.auto_gather_analytics,
        )


@pytest.mark.django_db
def test_schedule_gather_analytics_with_default_queue():
    with mock.patch(
        "aap_eda.tasks.analytics.utils.get_analytics_interval"
    ) as mock_interval, mock.patch(
        "aap_eda.tasks.analytics.tasking.enqueue_delay"
    ) as mock_enqueue, mock.patch(
        "aap_eda.tasks.analytics.flag_enabled",
        return_value=True,
    ):
        mock_interval.return_value = 300
        analytics.schedule_gather_analytics()

        mock_enqueue.assert_called_once_with(
            analytics.ANALYTICS_TASKS_QUEUE,
            analytics.ANALYTICS_SCHEDULE_JOB_ID,
            300,
            analytics.auto_gather_analytics,
        )


@pytest.mark.django_db
def test_schedule_gather_analytics_error_handling():
    with mock.patch(
        "aap_eda.tasks.analytics.utils.get_analytics_interval",
        return_value=5,
    ), mock.patch(
        "aap_eda.tasks.analytics.tasking.enqueue_delay"
    ) as mock_enqueue, mock.patch(
        "aap_eda.tasks.analytics.flag_enabled",
        return_value=True,
    ):
        mock_enqueue.side_effect = RuntimeError("Queue connection failed")

        with pytest.raises(RuntimeError) as exc_info:
            analytics.schedule_gather_analytics()

        assert "Queue connection failed" in str(exc_info.value)


@pytest.mark.django_db
def test_reschedule_gather_analytics():
    with mock.patch(
        "aap_eda.tasks.analytics.utils.get_analytics_interval"
    ) as mock_interval, mock.patch(
        "aap_eda.tasks.analytics.tasking.enqueue_delay"
    ) as mock_enqueue, mock.patch(
        "aap_eda.tasks.analytics.tasking.queue_cancel_job"
    ) as mock_cancel_job, mock.patch(
        "aap_eda.tasks.analytics.flag_enabled",
        return_value=True,
    ):
        mock_interval.return_value = 300
        analytics.reschedule_gather_analytics()

        mock_cancel_job.assert_called_once_with(
            analytics.ANALYTICS_TASKS_QUEUE,
            analytics.ANALYTICS_SCHEDULE_JOB_ID,
        )
        mock_enqueue.assert_called_once_with(
            analytics.ANALYTICS_TASKS_QUEUE,
            analytics.ANALYTICS_SCHEDULE_JOB_ID,
            300,
            analytics.auto_gather_analytics,
        )


@pytest.mark.parametrize(
    "tracking_state, expected_logs",
    [
        (True, ["Collecting EDA analytics", "Analytics collection is done"]),
        (False, ["INSIGHTS_TRACKING_STATE is not enabled"]),
    ],
    ids=["tracking_enabled", "tracking_disabled"],
)
def test_gather_analytics(tracking_state, expected_logs):
    with mock.patch(
        "aap_eda.tasks.analytics.utils.get_insights_tracking_state"
    ) as mock_tracking, mock.patch(
        "aap_eda.tasks.analytics.collector.gather"
    ) as mock_gather, mock.patch(
        "aap_eda.tasks.analytics.logger.info"
    ) as mock_logger:
        mock_tracking.return_value = tracking_state
        mock_gather.return_value = (
            ["file1.tgz", "file2.tgz"] if tracking_state else []
        )

        analytics._gather_analytics()

        for log in expected_logs:
            mock_logger.assert_any_call(log)


def test_gather_analytics_no_files():
    with mock.patch(
        "aap_eda.tasks.analytics.utils.get_insights_tracking_state",
        return_value=True,
    ), mock.patch(
        "aap_eda.tasks.analytics.collector.gather", return_value=[]
    ), mock.patch(
        "aap_eda.tasks.analytics.logger.info"
    ) as mock_logger:
        analytics._gather_analytics()
        mock_logger.assert_any_call("No analytics collected")
