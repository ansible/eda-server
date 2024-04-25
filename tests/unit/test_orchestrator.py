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

from datetime import datetime, timedelta
from unittest import mock

import pytest

from aap_eda.core.enums import ProcessParentType
from aap_eda.core.models import Activation, EventStream
from aap_eda.tasks.orchestrator import (
    UnknownProcessParentType,
    check_rulebook_queue_health,
    get_least_busy_queue_name,
    get_process_parent,
)
from tests.utils import mock_up_orchestrator_queues


@pytest.mark.parametrize(
    "queues",
    [
        {
            "queue": {
                "workers": {"worker": {"good": True}},
                "process_count": 1,
            },
        },
        {
            "queue1": {
                "workers": {"worker1_1": {"good": True}},
                "process_count": 1,
            },
            "queue2": {
                "workers": {"worker2_1": {"good": True}},
                "process_count": 2,
            },
        },
    ],
)
def test_get_least_busy_queue_name(monkeypatch, queues):
    mock_queues = mock_up_orchestrator_queues(queues, monkeypatch)

    queue_name = get_least_busy_queue_name()
    return


def test_get_process_parent_activation():
    activation_id = 1
    activation_mock = mock.Mock(spec=Activation)
    Activation.objects.get = mock.Mock(return_value=activation_mock)

    result = get_process_parent(ProcessParentType.ACTIVATION, activation_id)

    Activation.objects.get.assert_called_once_with(id=activation_id)
    assert result == activation_mock


def test_get_process_parent_event_stream():
    event_stream_id = 1
    event_stream_mock = mock.Mock(spec=EventStream)
    EventStream.objects.get = mock.Mock(return_value=event_stream_mock)

    result = get_process_parent(
        ProcessParentType.EVENT_STREAM,
        event_stream_id,
    )

    EventStream.objects.get.assert_called_once_with(id=event_stream_id)
    assert result == event_stream_mock


def test_get_process_parent_unknown_type():
    process_parent_type = "unknown"
    parent_id = 1

    with pytest.raises(UnknownProcessParentType) as exc_info:
        get_process_parent(process_parent_type, parent_id)

    assert (
        str(exc_info.value)
        == f"Unknown process parent type {process_parent_type}"
    )


@pytest.fixture
def setup_queue_health():
    queue_name = "rulebook_queue"
    queue_mock = mock.Mock()
    get_queue_mock = mock.Mock(return_value=queue_mock)
    settings_mock = mock.Mock()
    settings_mock.DEFAULT_WORKER_HEARTBEAT_TIMEOUT = 60
    datetime_mock = mock.Mock()
    timedelta_mock = mock.Mock()
    timedelta_mock.return_value = timedelta(seconds=60)

    patches = {
        "get_queue": mock.patch(
            "aap_eda.tasks.orchestrator.get_queue", get_queue_mock
        ),
        "datetime": mock.patch(
            "aap_eda.tasks.orchestrator.datetime", datetime_mock
        ),
        "timedelta": mock.patch(
            "aap_eda.tasks.orchestrator.timedelta", timedelta_mock
        ),
        "settings": mock.patch(
            "aap_eda.tasks.orchestrator.settings", settings_mock
        ),
    }
    with patches["get_queue"], patches["datetime"], patches[
        "timedelta"
    ], patches["settings"]:
        yield (
            queue_name,
            queue_mock,
            get_queue_mock,
            datetime_mock,
            settings_mock,
        )


def test_check_rulebook_queue_health_all_workers_dead(setup_queue_health):
    (
        queue_name,
        queue_mock,
        get_queue_mock,
        datetime_mock,
        _,
    ) = setup_queue_health

    # Specific setup for this test
    worker_mock = mock.Mock()
    worker_mock.last_heartbeat = datetime(2022, 1, 1)
    all_workers_mock = mock.Mock(return_value=[worker_mock])
    datetime_mock.now.return_value = datetime(2022, 1, 1, minute=5)

    with mock.patch("aap_eda.tasks.orchestrator.Worker.all", all_workers_mock):
        result = check_rulebook_queue_health(queue_name)

    get_queue_mock.assert_called_once_with(queue_name)
    all_workers_mock.assert_called_once_with(queue=queue_mock)
    queue_mock.empty.assert_called_once()
    assert result is False


def test_check_rulebook_queue_health_some_workers_alive(setup_queue_health):
    (
        queue_name,
        queue_mock,
        get_queue_mock,
        datetime_mock,
        _,
    ) = setup_queue_health

    # Specific setup for this test
    worker_mock1 = mock.Mock()
    worker_mock1.last_heartbeat = datetime(2022, 1, 1, hour=6)
    worker_mock2 = mock.Mock()
    worker_mock2.last_heartbeat = datetime(2022, 1, 1)
    all_workers_mock = mock.Mock(return_value=[worker_mock1, worker_mock2])
    datetime_mock.now.return_value = datetime(2022, 1, 1, hour=6, second=30)

    with mock.patch("aap_eda.tasks.orchestrator.Worker.all", all_workers_mock):
        result = check_rulebook_queue_health(queue_name)

    get_queue_mock.assert_called_once_with(queue_name)
    all_workers_mock.assert_called_once_with(queue=queue_mock)
    queue_mock.empty.assert_not_called()
    assert result is True
