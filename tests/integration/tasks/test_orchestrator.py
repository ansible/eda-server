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
from aap_eda.core import models
from aap_eda.core.enums import ActivationRequest, ActivationStatus
from aap_eda.tasks import orchestrator


@pytest.fixture()
def source():
    user = models.User.objects.create_user(
        username="obi-wan.kenobi",
        first_name="Obi-Wan",
        last_name="Kenobi",
        email="",
        password="secret",
    )
    source = models.Source.objects.create(
        name="test-source1",
        type="ansible.eda.generic",
        args='{"a": 1, "b": 2}',
        user=user,
    )
    return source


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
        status = (
            ActivationStatus.STARTING if i == 0 else ActivationStatus.RUNNING
        )
        activations.append(
            models.Activation.objects.create(
                name=f"running{i}",
                user=user,
                status=status,
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
@mock.patch("aap_eda.tasks.orchestrator.ActivationManager")
def test_manage_request(manager_mock, activation, verb):
    proxy = models.ProcessParentProxy(activation)
    queue.push(proxy, verb)
    manager_instance_mock = mock.Mock()
    manager_mock.return_value = manager_instance_mock

    orchestrator._manage(proxy.to_dict())
    manager_mock.assert_called_once()
    called_args, _ = manager_mock.call_args
    assert called_args[0].id == proxy.id

    if verb == ActivationRequest.START:
        manager_instance_mock.start.assert_called_once_with(is_restart=False)
    elif verb == ActivationRequest.RESTART:
        manager_instance_mock.restart.assert_called_once()
    elif verb == ActivationRequest.STOP:
        manager_instance_mock.stop.assert_called_once()
    elif verb == ActivationRequest.DELETE:
        manager_instance_mock.delete.assert_called_once()
    elif verb == ActivationRequest.AUTO_START:
        manager_instance_mock.start.assert_called_once_with(is_restart=True)
    assert len(queue.peek_all(proxy)) == 0


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.ActivationManager")
def test_manage_not_start(manager_mock, activation, max_running_activations):
    proxy = models.ProcessParentProxy(activation)
    queue.push(proxy, ActivationRequest.START)
    manager_instance_mock = mock.Mock()
    manager_mock.return_value = manager_instance_mock

    orchestrator._manage(proxy.to_dict())

    manager_instance_mock.start.assert_not_called()
    assert len(queue.peek_all(proxy)) == 1


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
    proxy = models.ProcessParentProxy(activation)
    command(proxy)
    enqueue_args = [
        "activation",
        orchestrator._manage_activation_job_id(proxy),
        orchestrator._manage,
    ]
    enqueue_mock.assert_called_once_with(
        *enqueue_args,
        process_parent_data=proxy.to_dict(),
    )

    queued = models.ActivationRequestQueue.objects.first()
    assert queued.activation == activation
    assert queued.request == queued_request


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.unique_enqueue")
def test_monitor_activations(
    enqueue_mock,
    activation,
    source,
    max_running_activations,
):
    proxy_activation = models.ProcessParentProxy(activation)
    proxy_source = models.ProcessParentProxy(source)
    call_args = [
        mock.call(
            "activation",
            orchestrator._manage_activation_job_id(proxy_activation),
            orchestrator._manage,
            process_parent_data=proxy_activation.to_dict(),
        ),
    ]
    for running in max_running_activations:
        running_proxy = models.ProcessParentProxy(running)
        call_args.append(
            mock.call(
                "activation",
                orchestrator._manage_activation_job_id(running_proxy),
                orchestrator._manage,
                process_parent_data=running_proxy.to_dict(),
            ),
        )

    queue.push(proxy_activation, ActivationRequest.START)
    queue.push(proxy_source, ActivationRequest.START)
    for running in max_running_activations:
        running_proxy = models.ProcessParentProxy(running)
        queue.push(running_proxy, ActivationRequest.START)

    orchestrator.monitor_activations()
    enqueue_mock.assert_has_calls(call_args, any_order=True)
