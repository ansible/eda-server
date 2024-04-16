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

import pytest

import aap_eda.tasks.activation_request_queue as queue
from aap_eda.core import models
from aap_eda.core.enums import ActivationRequest, ProcessParentType


@pytest.fixture()
def activations():
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    activation1 = models.Activation.objects.create(
        name="test1",
        user=user,
    )

    activation2 = models.Activation.objects.create(
        name="test2",
        user=user,
    )

    return [activation1, activation2]


@pytest.mark.django_db
def test_queue(activations):
    queue.push(
        ProcessParentType.ACTIVATION, activations[0].id, ActivationRequest.STOP
    )
    queue.push(
        ProcessParentType.ACTIVATION,
        activations[1].id,
        ActivationRequest.DELETE,
    )
    queue.push(
        ProcessParentType.ACTIVATION,
        activations[0].id,
        ActivationRequest.START,
    )
    assert models.ActivationRequestQueue.objects.count() == 3
    requests = queue.list_requests()
    assert len(requests) == 2
    assert requests[0].process_parent_id == activations[0].id
    assert requests[1].process_parent_id == activations[1].id
    assert requests[0].request == ActivationRequest.STOP
    assert requests[1].request == ActivationRequest.DELETE

    requests = queue.peek_all(ProcessParentType.ACTIVATION, activations[0].id)
    assert len(requests) == 2

    queue.pop_until(
        ProcessParentType.ACTIVATION, activations[0].id, requests[1].id
    )
    assert (
        len(queue.peek_all(ProcessParentType.ACTIVATION, activations[0].id))
        == 0
    )


@pytest.mark.parametrize(
    "requests",
    [
        {
            "queued": [ActivationRequest.AUTO_START],
            "dequeued": [ActivationRequest.AUTO_START],
        },
        {"queued": [], "dequeued": []},
        {
            "queued": [
                ActivationRequest.START,
                ActivationRequest.STOP,
                ActivationRequest.STOP,
                ActivationRequest.DELETE,
            ],
            "dequeued": [ActivationRequest.DELETE],
        },
        {
            "queued": [
                ActivationRequest.DELETE,
                ActivationRequest.STOP,
                ActivationRequest.STOP,
                ActivationRequest.START,
            ],
            "dequeued": [ActivationRequest.DELETE],
        },
        {
            "queued": [
                ActivationRequest.AUTO_START,
                ActivationRequest.RESTART,
                ActivationRequest.STOP,
                ActivationRequest.AUTO_START,
                ActivationRequest.START,
            ],
            "dequeued": [
                ActivationRequest.STOP,
                ActivationRequest.START,
            ],
        },
        {
            "queued": [
                ActivationRequest.RESTART,
                ActivationRequest.START,
            ],
            "dequeued": [
                ActivationRequest.RESTART,
            ],
        },
    ],
)
@pytest.mark.django_db
def test_arbitrate(activations, requests):
    for request in requests["queued"]:
        queue.push(ProcessParentType.ACTIVATION, activations[0].id, request)
    dequeued = queue.peek_all(ProcessParentType.ACTIVATION, activations[0].id)
    dequeued_requests = [entry.request for entry in dequeued]
    assert dequeued_requests == requests["dequeued"]
    assert models.ActivationRequestQueue.objects.count() == len(
        requests["dequeued"]
    )
