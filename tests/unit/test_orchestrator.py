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
import uuid
from datetime import datetime, timedelta
from unittest import mock

import django_rq
import pytest
from django.conf import settings

from aap_eda.core.enums import ActivationStatus, ProcessParentType
from aap_eda.core.models import Activation, RulebookProcess
from aap_eda.settings import default
from aap_eda.tasks import orchestrator
from aap_eda.tasks.exceptions import UnknownProcessParentType
from aap_eda.tasks.orchestrator import (
    _manage,
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

    monkeypatch.setattr(django_rq, "get_queue", _get_queue)

    def _worker_all(queue=None) -> list:
        return queue.workers

    monkeypatch.setattr(orchestrator.tasking.Worker, "all", _worker_all)

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
                "workers": {
                    "worker": {"responsive": True},
                },
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
                "workers": {
                    "worker1_1": {"responsive": True},
                },
                "process_count": 1,
            },
            "queue2": {
                "workers": {
                    "worker2_1": {"responsive": True},
                },
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
                "workers": {
                    "worker1_1": {"responsive": True},
                },
                "process_count": 1,
            },
            "queue2": {
                "workers": {
                    "worker2_1": {"responsive": False},
                },
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
                "workers": {
                    "worker1_1": {"responsive": True},
                },
                "process_count": 2,
            },
            "queue2": {
                "workers": {
                    "worker2_1": {"responsive": False},
                },
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
                "workers": {
                    "worker1_1": {"responsive": False},
                },
                "process_count": 1,
            },
            "queue2": {
                "workers": {
                    "worker2_1": {"responsive": False},
                },
                "process_count": 1,
            },
        },
    )


@pytest.fixture
def three_queues_two_candidates(monkeypatch):
    return _mock_up_queues(
        monkeypatch,
        {
            "queue1": {
                "workers": {
                    "worker1_1": {"responsive": True},
                },
                "process_count": 1,
            },
            "queue2": {
                "workers": {
                    "worker2_1": {"responsive": True},
                },
                "process_count": 1,
            },
            "queue3": {
                "workers": {
                    "worker3_1": {"responsive": True},
                },
                "process_count": 2,
            },
        },
    )


@pytest.fixture
def process_parent():
    parent = mock.Mock(spec=Activation)
    parent.id = 1
    parent.status = ActivationStatus.RUNNING
    parent.log_tracking_id = str(uuid.uuid4())
    return parent


@pytest.fixture
def mock_get_parent():
    with mock.patch(
        "aap_eda.tasks.orchestrator.get_process_parent"
    ) as mock_get:
        yield mock_get


@pytest.fixture
def mock_requests_queue():
    with mock.patch("aap_eda.tasks.orchestrator.requests_queue") as mock_queue:
        yield mock_queue


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
@pytest.mark.django_db
def test_get_least_busy_queue_name(fixture, request):
    queues = request.getfixturevalue(fixture)

    responsive_queues = [
        queue
        for queue in queues.values()
        if sum(1 for _ in filter(lambda w: w.responsive, queue.workers)) > 0
    ]

    if responsive_queues:
        expected_queue = min(responsive_queues, key=lambda q: q.count())
        assert get_least_busy_queue_name() == expected_queue.name
    else:
        from aap_eda.tasks.orchestrator import HealthyQueueNotFoundError

        with pytest.raises(HealthyQueueNotFoundError):
            get_least_busy_queue_name()


@pytest.mark.django_db
def test_get_least_busy_queue_name_multiple_queues(
    three_queues_two_candidates,
):
    expected_queues = [
        "queue1",
        "queue2",
    ]
    queue = get_least_busy_queue_name()
    assert queue in expected_queues


@pytest.fixture
def multi_queue_various_states(monkeypatch):
    return _mock_up_queues(
        monkeypatch,
        {
            "good1": {
                "workers": {
                    "good1_1": {"responsive": True},
                },
                "process_count": 1,
            },
            "good2": {
                "workers": {
                    "good2_1": {"responsive": True},
                    "good2_2": {"responsive": True},
                    "good2_3": {"responsive": False},
                },
                "process_count": 1,
            },
            "good3": {
                "workers": {
                    "good3_1": {"responsive": False},
                    "good3_2": {"responsive": False},
                    "good3_3": {"responsive": True},
                },
                "process_count": 1,
            },
            "bad1": {
                "workers": {
                    "bad1_1": {"responsive": False},
                },
                "process_count": 1,
            },
            "bad2": {
                "workers": {
                    "bad2_1": {"responsive": False},
                    "bad2_2": {"responsive": False},
                    "bad2_3": {"responsive": False},
                },
                "process_count": 1,
            },
        },
    )


@pytest.mark.django_db
def test_check_rulebook_queue_health(multi_queue_various_states):
    queues = multi_queue_various_states

    expected_good_queues = [
        queue
        for queue in queues.values()
        if sum(1 for _ in filter(lambda w: w.responsive, queue.workers)) > 0
    ]
    expected_bad_queues = [
        queue
        for queue in queues.values()
        if sum(1 for _ in filter(lambda w: w.responsive, queue.workers)) == 0
    ]

    found_good_queues = []
    found_bad_queues = []
    for queue in queues.values():
        if check_rulebook_queue_health(queue.name):
            found_good_queues.append(queue)
        else:
            found_bad_queues.append(queue)

    assert len(found_good_queues) == len(expected_good_queues)
    assert len(
        [x for x in expected_good_queues if x in found_good_queues]
    ) == len(expected_good_queues)

    assert len(found_bad_queues) == len(expected_bad_queues)
    assert len(
        [x for x in expected_bad_queues if x in found_bad_queues]
    ) == len(expected_bad_queues)
    for queue in found_bad_queues:
        assert queue.count() == 0


def test_get_process_parent_activation():
    activation_id = 1
    activation_mock = mock.Mock(spec=Activation)
    Activation.objects.get = mock.Mock(return_value=activation_mock)

    result = get_process_parent(ProcessParentType.ACTIVATION, activation_id)

    Activation.objects.get.assert_called_once_with(id=activation_id)
    assert result == activation_mock


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
        "get_queue": mock.patch("django_rq.get_queue", get_queue_mock),
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

    with mock.patch(
        "aap_eda.tasks.orchestrator.tasking.Worker.all", all_workers_mock
    ):
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

    with mock.patch(
        "aap_eda.tasks.orchestrator.tasking.Worker.all", all_workers_mock
    ):
        result = check_rulebook_queue_health(queue_name)

    get_queue_mock.assert_called_once_with(queue_name)
    all_workers_mock.assert_called_once_with(queue=queue_mock)
    queue_mock.empty.assert_not_called()
    assert result is True


@pytest.mark.django_db
def test_manage_monitor_called_with_no_requests(
    process_parent, mock_get_parent, mock_requests_queue
):
    mock_get_parent.return_value = process_parent
    mock_requests_queue.peek_all.return_value = []
    manager_mock = mock.Mock()

    with mock.patch(
        "aap_eda.tasks.orchestrator.ActivationManager"
    ) as mock_manager, mock.patch(
        "aap_eda.tasks.orchestrator.assign_request_id"
    ) as mock_assign_req, mock.patch(
        "aap_eda.tasks.orchestrator.assign_log_tracking_id"
    ) as mock_assign_log:
        mock_manager.return_value = manager_mock
        _manage(ProcessParentType.ACTIVATION, 1, "x_request_id")

    mock_assign_req.assert_called_once_with("x_request_id")
    mock_assign_log.assert_called_once_with(process_parent.log_tracking_id)
    manager_mock.monitor.assert_called_once()
