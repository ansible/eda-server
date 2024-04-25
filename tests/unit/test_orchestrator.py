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

import functools
from datetime import datetime, timedelta
from unittest import mock

import pytest
from django.conf import settings

from aap_eda.core.enums import ProcessParentType
from aap_eda.core.models import Activation, EventStream, RulebookProcess
from aap_eda.settings import default
from aap_eda.tasks import orchestrator
from aap_eda.tasks.orchestrator import (
    HealthyQueueNotFoundError,
    UnknownProcessParentType,
    check_rulebook_queue_health,
    get_least_busy_queue_name,
    get_process_parent,
)


# Sets up a collection of mocked queues in specified states for testing
# orchestrator functionality.
#
# Queues are specified via a dictionary using the following format.
# Any number of queues may be specified.
#
# {                                                             # noqa: E800
#     "queue1": {                                               # noqa: E800
#         "workers": {                                          # noqa: E800
#             "worker1_1": {                                    # noqa: E800
#                 "responsive": True,                           # noqa: E800
#             },                                                # noqa: E800
#         },                                                    # noqa: E800
#         "process_count": 1,                                   # noqa: E800
#     },                                                        # noqa: E800
#     "queue2": {                                               # noqa: E800
#         "workers": {                                          # noqa: E800
#             "worker2_1": {                                    # noqa: E800
#                 "responsive": True,                           # noqa: E800
#             },                                                # noqa: E800
#         },                                                    # noqa: E800
#         "process_count": 2,                                   # noqa: E800
#     },                                                        # noqa: E800
# }                                                             # noqa: E800
#
def _mock_up_queues(monkeypatch, queues):
    mock_queues = {}

    monkeypatch.setattr(
        settings, "RULEBOOK_WORKER_QUEUES", list(queues.keys())
    )

    def _process_object_filter(**kwargs) -> mock.Mock:
        return mock_queues[kwargs.get("rulebookprocessqueue__queue_name")]

    monkeypatch.setattr(
        RulebookProcess.objects, "filter", _process_object_filter
    )

    def _get_queue(name: str) -> mock.Mock:
        return mock_queues[name]

    monkeypatch.setattr(orchestrator, "get_queue", _get_queue)

    def _worker_all(queue=None) -> list:
        return queue.workers

    monkeypatch.setattr(orchestrator.Worker, "all", _worker_all)

    def _process_count(queue: mock.Mock) -> None:
        return queue.process_count

    def _empty_queue(queue: mock.Mock) -> None:
        queue.process_count = 0

    for queue_name in queues.keys():
        mock_queue = mock.Mock()
        mock_queue.name = queue_name
        mock_queue.process_count = queues[queue_name]["process_count"]
        mock_queue.count = functools.partial(_process_count, mock_queue)
        mock_queue.empty = functools.partial(_empty_queue, mock_queue)

        mock_queue.workers = []

        for worker_name in queues[queue_name]["workers"].keys():
            mock_worker = mock.Mock()
            mock_worker.name = worker_name
            mock_worker.responsive = queues[queue_name]["workers"][
                worker_name
            ]["responsive"]
            mock_worker.last_heartbeat = datetime.now()
            if not mock_worker.responsive:
                mock_worker.last_heartbeat -= timedelta(
                    seconds=(2 * default.DEFAULT_WORKER_HEARTBEAT_TIMEOUT)
                )
            mock_queue.workers.append(mock_worker)

        mock_queues[queue_name] = mock_queue

    return mock_queues


@pytest.fixture
def one_queue(monkeypatch):
    return _mock_up_queues(
        monkeypatch,
        {
            "queue": {
                "workers": {"worker": {"responsive": True}},
                "process_count": 1,
            },
        },
    )


@pytest.fixture
def two_queues_differing_counts(monkeypatch):
    return _mock_up_queues(
        monkeypatch,
        {
            "queue1": {
                "workers": {"worker1_1": {"responsive": True}},
                "process_count": 1,
            },
            "queue2": {
                "workers": {"worker2_1": {"responsive": True}},
                "process_count": 2,
            },
        },
    )


@pytest.fixture
def two_queues_one_responsive(monkeypatch):
    return _mock_up_queues(
        monkeypatch,
        {
            "queue1": {
                "workers": {"worker1_1": {"responsive": True}},
                "process_count": 1,
            },
            "queue2": {
                "workers": {"worker2_1": {"responsive": False}},
                "process_count": 1,
            },
        },
    )


@pytest.fixture
def two_queues_one_responsive_higher_count(monkeypatch):
    return _mock_up_queues(
        monkeypatch,
        {
            "queue1": {
                "workers": {"worker1_1": {"responsive": True}},
                "process_count": 2,
            },
            "queue2": {
                "workers": {"worker2_1": {"responsive": False}},
                "process_count": 1,
            },
        },
    )


@pytest.fixture
def two_queues_neither_responsive(monkeypatch):
    return _mock_up_queues(
        monkeypatch,
        {
            "queue1": {
                "workers": {"worker1_1": {"responsive": False}},
                "process_count": 1,
            },
            "queue2": {
                "workers": {"worker2_1": {"responsive": False}},
                "process_count": 1,
            },
        },
    )


@pytest.mark.parametrize(
    "fixture",
    [
        "one_queue",
        "two_queues_differing_counts",
        "two_queues_one_responsive",
        "two_queues_one_responsive_higher_count",
        "two_queues_neither_responsive",
    ],
)
def test_get_least_busy_queue_name(fixture, request):
    queues = request.getfixturevalue(fixture)

    responsive_queues = [
        queue
        for queue in queues.values()
        if len([worker for worker in queue.workers if worker.responsive]) > 0
    ]

    if responsive_queues:
        expected_queue = min(responsive_queues, key=lambda q: q.count())
        assert get_least_busy_queue_name() == expected_queue.name
    else:
        with pytest.raises(HealthyQueueNotFoundError):
            get_least_busy_queue_name()


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
