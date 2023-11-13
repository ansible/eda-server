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
@pytest.mark.parametrize(
    "verb",
    [
        ActivationRequest.START,
        ActivationRequest.RESTART,
        ActivationRequest.STOP,
        ActivationRequest.DELETE,
        ActivationRequest.AUTO_START,
    ],
)
@mock.patch("aap_eda.services.activation.manager.ActivationManager")
def test_manage_request(manager_mock, activation, verb):
    queue.push(activation.id, verb)
    manager_instance_mock = mock.Mock()
    manager_mock.return_value = manager_instance_mock

    orchestrator._manage(activation.id)

    manager_mock.assert_called_once_with(activation)
    if verb == ActivationRequest.START:
        manager_instance_mock.start.assert_called_once_with(False)
    elif verb == ActivationRequest.RESTART:
        manager_instance_mock.restart.assert_called_once()
    elif verb == ActivationRequest.STOP:
        manager_instance_mock.stop.assert_called_once()
    elif verb == ActivationRequest.DELETE:
        manager_instance_mock.delete.assert_called_once()
    elif verb == ActivationRequest.AUTO_START:
        manager_instance_mock.start.assert_called_once_with(True)
    assert len(queue.peek_all(activation.id)) == 0


@pytest.mark.django_db
@mock.patch("aap_eda.services.activation.manager.ActivationManager")
def test_manage_not_start(manager_mock, activation, max_running_activations):
    queue.push(activation.id, ActivationRequest.START)
    manager_instance_mock = mock.Mock()
    manager_mock.return_value = manager_instance_mock

    orchestrator._manage(activation.id)

    manager_mock.assert_called_once_with(activation)
    manager_instance_mock.monitor.assert_called_once()
    manager_instance_mock.start.assert_not_called()
    assert len(queue.peek_all(activation.id)) == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "command, queued_request",
    [
        (orchestrator.start_activation, ActivationRequest.START),
        (orchestrator.stop_activation, ActivationRequest.STOP),
        (orchestrator.start_activation, ActivationRequest.START),
        (orchestrator.delete_activation, ActivationRequest.DELETE),
        (orchestrator.restart_activation, ActivationRequest.RESTART),
    ],
)
@mock.patch("aap_eda.tasks.orchestrator.unique_enqueue")
def test_activation_requests(
    enqueue_mock, activation, command, queued_request
):
    command(activation.id)
    enqueue_args = [
        "activation",
        orchestrator._manage_activation_job_id(activation.id),
        orchestrator._manage,
        activation.id,
    ]
    enqueue_mock.assert_called_once_with(*enqueue_args)

    queued = models.ActivationRequestQueue.objects.first()
    assert queued.activation == activation
    assert queued.request == queued_request


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.enqueue_delay")
def test_system_restart_activation(enqueue_mock, activation):
    orchestrator.system_restart_activation(activation.id, 5)
    enqueue_args = [
        "default",
        5,
        orchestrator.auto_start_activation,
        activation.id,
    ]
    enqueue_mock.assert_called_once_with(*enqueue_args)


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.unique_enqueue")
def test_monitor_activations(
    enqueue_mock, activation, max_running_activations
):
    call_args = [
        mock.call(
            "activation",
            orchestrator._manage_activation_job_id(activation.id),
            orchestrator._manage,
            activation.id,
        )
    ]
    for running in max_running_activations:
        call_args.append(
            mock.call(
                "activation",
                orchestrator._manage_activation_job_id(running.id),
                orchestrator._manage,
                running.id,
            )
        )

    queue.push(activation.id, ActivationRequest.START)
    orchestrator.monitor_activations()

    enqueue_mock.assert_has_calls(call_args, any_order=True)
