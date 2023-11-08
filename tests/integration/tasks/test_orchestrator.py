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

from unittest import mock

import pytest
from django.conf import settings

import aap_eda.tasks.activation_request_queue as queue
import aap_eda.tasks.orchestrator as orchestrator
from aap_eda.core import models
from aap_eda.core.enums import ActivationRequest, ActivationStatus


@pytest.fixture()
def activation():
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    return models.Activation.objects.create(
        name="test1",
        user=user,
    )


@pytest.fixture()
def max_running_activations():
    user = models.User.objects.create_user(
        username="luke.skywalker2",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    activations = []
    for i in range(settings.MAX_RUNNING_ACTIVATIONS):
        activations.append(
            models.Activation.objects.create(
                name=f"running{i}",
                user=user,
                status=ActivationStatus.RUNNING,
            )
        )
    return activations


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.ActivationManager")
def test_manage_start(manager_mock, activation):
    queue.push(activation.id, ActivationRequest.START)
    manager_instance_mock = mock.Mock()
    manager_mock.return_value = manager_instance_mock
    manager_instance_mock.start.return_value = mock.Mock()

    orchestrator._manage(activation.id)

    manager_mock.assert_called_once_with(activation)
    manager_instance_mock.start.assert_called_once()
    assert len(queue.peek_all(activation.id)) == 0


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.ActivationManager")
def test_manage_not_start(manager_mock, activation, max_running_activations):
    queue.push(activation.id, ActivationRequest.START)
    manager_instance_mock = mock.Mock()
    manager_mock.return_value = manager_instance_mock
    manager_instance_mock.monitor.return_value = mock.Mock()
    manager_instance_mock.start.return_value = mock.Mock()

    orchestrator._manage(activation.id)

    manager_mock.assert_called_once_with(activation)
    manager_instance_mock.monitor.assert_called_once()
    manager_instance_mock.start.assert_not_called()
    assert len(queue.peek_all(activation.id)) == 1
