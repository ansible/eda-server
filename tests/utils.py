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

from aap_eda.core.models import RulebookProcess
from aap_eda.settings import default
from aap_eda.tasks import orchestrator


# Sets up a collection of mocked queues in specified states for testing
# orchestrator functionality.
#
# Queues are specified via a dictionary using the following format.
# Any number of queues may be specified.
#
# {
#     "queue1": {
#         "workers": {
#             "worker1_1": {
#                 "responsive": True
#             }
#         },
#         "process_count": 1
#     },
#     "queue2": {
#         "workers": {
#             "worker2_1": {
#                 "responsive": True
#             }
#         },
#         "process_count": 2
# }
#
def mock_up_orchestrator_queues(queues, monkeypatch):
    mock_queues = {}

    monkeypatch.setattr(default, "RULEBOOK_WORKER_QUEUES", list(queues.keys()))

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
        mock_queues[queue_name] = mock.Mock()
        mock_queues[queue_name].process_count = queues[queue_name][
            "process_count"
        ]
        mock_queues[queue_name].count = functools.partial(
            _process_count, mock_queues[queue_name]
        )
        mock_queues[queue_name].empty = functools.partial(
            _empty_queue, mock_queues[queue_name]
        )

        mock_queues[queue_name].workers = []

        for worker_name in queues[queue_name]["workers"].keys():
            mock_worker = mock.Mock()
            mock_worker.name = worker_name
            mock_worker.last_heartbeat = datetime.now()
            if not queues[queue_name]["workers"][worker_name]["responsive"]:
                mock_worker.last_heartbeat -= timedelta(
                    seconds=(2 * default.DEFAULT_WORKER_HEARTBEAT_TIMEOUT)
                )
            mock_queues[queue_name].workers.append(mock_worker)

    return mock_queues
