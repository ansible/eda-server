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

MODEL_NAME = "aap_eda.core.models.activation.Activation"


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
def max_running_processes():
    user = models.User.objects.create_user(
        username="luke.skywalker2",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    activation = models.Activation.objects.create(
        name="test",
        user=user,
    )
    processes = []
    for i in range(settings.MAX_RUNNING_ACTIVATIONS):
        status = (
            ActivationStatus.STARTING if i == 0 else ActivationStatus.RUNNING
        )
        processes.append(
            models.RulebookProcess.objects.create(
                name=f"running{i}",
                activation=activation,
                status=status,
            )
        )
    return processes


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
    queue.push(MODEL_NAME, activation.id, verb)
    manager_instance_mock = mock.Mock()
    manager_mock.return_value = manager_instance_mock

    orchestrator._manage(MODEL_NAME, activation.id)

    manager_mock.assert_called_once_with(activation)
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
    assert len(queue.peek_all(MODEL_NAME, activation.id)) == 0


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.ActivationManager")
def test_manage_not_start(manager_mock, activation, max_running_processes):
    queue.push(MODEL_NAME, activation.id, ActivationRequest.START)
    manager_instance_mock = mock.Mock()
    manager_mock.return_value = manager_instance_mock

    orchestrator._manage(MODEL_NAME, activation.id)

    manager_instance_mock.start.assert_not_called()
    assert len(queue.peek_all(MODEL_NAME, activation.id)) == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "command, queued_request",
    [
        (orchestrator.start_rulebook_process, ActivationRequest.START),
        (orchestrator.stop_rulebook_process, ActivationRequest.STOP),
        (orchestrator.start_rulebook_process, ActivationRequest.START),
        (orchestrator.delete_rulebook_process, ActivationRequest.DELETE),
        (orchestrator.restart_rulebook_process, ActivationRequest.RESTART),
    ],
)
@mock.patch("aap_eda.tasks.orchestrator.unique_enqueue")
def test_activation_requests(
    enqueue_mock, activation, command, queued_request
):
    command(MODEL_NAME, activation.id)
    enqueue_args = [
        "activation",
        orchestrator._manage_process_job_id(MODEL_NAME, activation.id),
        orchestrator._manage,
        MODEL_NAME,
        activation.id,
    ]
    enqueue_mock.assert_called_once_with(*enqueue_args)

    queued = models.ActivationRequestQueue.objects.first()
    assert queued.process_parent_fqcn == MODEL_NAME
    assert queued.process_parent_id == activation.id
    assert queued.request == queued_request


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.unique_enqueue")
def test_monitor_rulebook_processes(
    enqueue_mock, activation, max_running_processes
):
    call_args = [
        mock.call(
            "activation",
            orchestrator._manage_process_job_id(MODEL_NAME, activation.id),
            orchestrator._manage,
            MODEL_NAME,
            activation.id,
        )
    ]
    for running in max_running_processes:
        call_args.append(
            mock.call(
                "activation",
                orchestrator._manage_process_job_id(MODEL_NAME, running.id),
                orchestrator._manage,
                MODEL_NAME,
                running.id,
            )
        )

    queue.push(MODEL_NAME, activation.id, ActivationRequest.START)
    for running in max_running_processes:
        queue.push(MODEL_NAME, running.id, ActivationRequest.START)
    orchestrator.monitor_rulebook_processes()

    enqueue_mock.assert_has_calls(call_args, any_order=True)
