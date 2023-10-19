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
from aap_eda.core.enums import ActivationRequest


@pytest.fixture()
def init_activations():
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
def test_queue(init_activations):
    queue.push(init_activations[0].id, ActivationRequest.START)
    queue.push(init_activations[1].id, ActivationRequest.STOP)
    queue.push(init_activations[0].id, ActivationRequest.DELETE)
    queue.push(init_activations[0].id, ActivationRequest.RESTART)
    assert models.ActivationRequestQueue.objects.count() == 4
    assert queue.list_activations() == [
        init_activations[0].id,
        init_activations[1].id,
    ]

    requests = queue.peek_all(init_activations[0].id)
    assert len(requests) == 3

    queue.pop_until(init_activations[0].id, requests[1].id)
    assert len(queue.peek_all(init_activations[0].id)) == 1
