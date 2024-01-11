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

import uuid

import pytest

import aap_eda.tasks.activation_request_queue as queue
from aap_eda.core import models
from aap_eda.core.enums import ActivationRequest


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


@pytest.fixture()
def sources():
    user = models.User.objects.create_user(
        username="obi-wan.kenobi",
        first_name="Obi-Wan",
        last_name="Kenobi",
        email="obi-wan@example.com",
        password="secret",
    )

    source1 = models.Source.objects.create(
        uuid=uuid.uuid4(),
        name="test-source1",
        type="ansible.eda.generic",
        args='{"a": 1, "b": 2}',
        user=user,
    )

    source2 = models.Source.objects.create(
        uuid=uuid.uuid4(),
        name="test-source2",
        type="ansible.eda.generic",
        args='{"a": 2, "b": 3}',
        user=user,
    )

    return [source1, source2]


@pytest.mark.django_db
def test_queue(activations, sources):
    proxy_activation_0 = models.ProcessParentProxy(activations[0])
    proxy_activation_1 = models.ProcessParentProxy(activations[1])
    proxy_source_0 = models.ProcessParentProxy(sources[0])
    proxy_source_1 = models.ProcessParentProxy(sources[1])

    queue.push(proxy_activation_0, ActivationRequest.STOP)
    queue.push(proxy_activation_1, ActivationRequest.DELETE)
    queue.push(proxy_activation_0, ActivationRequest.START)

    queue.push(proxy_source_0, ActivationRequest.STOP)
    queue.push(proxy_source_1, ActivationRequest.DELETE)
    queue.push(proxy_source_0, ActivationRequest.START)

    assert models.ActivationRequestQueue.objects.count() == 6
    names = [item.name for item in queue.list_activations()]
    assert len(names) == 4
    assert names == [
        item.name for group in [activations, sources] for item in group
    ]

    requests = queue.peek_all(proxy_activation_0)
    assert len(requests) == 2

    queue.pop_until(proxy_activation_0, requests[1].id)
    assert models.ActivationRequestQueue.objects.count() == 4
    assert len(queue.peek_all(proxy_activation_0)) == 0
    assert len(queue.peek_all(proxy_source_0)) == 2
    assert len(queue.list_activations()) == 3


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
    proxy_activation = models.ProcessParentProxy(activations[0])
    for request in requests["queued"]:
        queue.push(proxy_activation, request)
    dequeued = queue.peek_all(proxy_activation)
    dequeued_requests = [entry.request for entry in dequeued]
    assert dequeued_requests == requests["dequeued"]
    assert models.ActivationRequestQueue.objects.count() == len(
        requests["dequeued"],
    )
