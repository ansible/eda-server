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
from aap_eda.core.enums import (
    ActivationRequest,
    ActivationStatus,
    ProcessParentType,
)
from aap_eda.tasks import orchestrator


@pytest.fixture
def default_rulebook() -> models.Rulebook:
    """Return a default rulebook."""
    rulesets = """
---
- name: Hello World
  hosts: all
  sources:
    - ansible.eda.range:
        limit: 5
  rules:
    - name: Say Hello
      condition: event.i == 1
      action:
        debug:
          msg: "Hello World!"

"""
    return models.Rulebook.objects.create(
        name="test-rulebook",
        rulesets=rulesets,
    )


@pytest.fixture()
def activation(default_rulebook):
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    decision_environment = models.DecisionEnvironment.objects.create(
        name="test-decision-environment",
        image_url="localhost:14000/test-image-url",
    )
    return models.Activation.objects.create(
        name="test1",
        user=user,
        decision_environment=decision_environment,
        rulebook=default_rulebook,
        rulebook_rulesets=default_rulebook.rulesets,
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
        models.RulebookProcessQueue.objects.create(
            process=processes[-1],
            queue_name="queue_name_test",
        )
    return processes


@pytest.fixture
def job_mock():
    mock_job = mock.MagicMock()
    mock_job.origin = "queue_name_test"
    return mock_job


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
    queue.push(ProcessParentType.ACTIVATION, activation.id, verb)
    manager_instance_mock = mock.Mock()
    manager_mock.return_value = manager_instance_mock

    orchestrator._manage(ProcessParentType.ACTIVATION, activation.id)

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
    assert (
        len(queue.peek_all(ProcessParentType.ACTIVATION, activation.id)) == 0
    )


@pytest.mark.django_db
@mock.patch.object(orchestrator.ActivationManager, "start", autospec=True)
def test_manage_not_start(
    start_mock,
    job_mock,
    activation,
    max_running_processes,
):
    queue.push(
        ProcessParentType.ACTIVATION, activation.id, ActivationRequest.START
    )

    with mock.patch(
        "aap_eda.services.activation.activation_manager.get_current_job",
        return_value=job_mock,
    ):
        orchestrator._manage(ProcessParentType.ACTIVATION, activation.id)

    start_mock.assert_not_called()
    assert (
        len(queue.peek_all(ProcessParentType.ACTIVATION, activation.id)) == 1
    )


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
    command(ProcessParentType.ACTIVATION, activation.id)
    enqueue_args = [
        "activation",
        orchestrator._manage_process_job_id(
            ProcessParentType.ACTIVATION, activation.id
        ),
        orchestrator._manage,
        ProcessParentType.ACTIVATION,
        activation.id,
    ]
    enqueue_mock.assert_called_once_with(*enqueue_args)

    queued = models.ActivationRequestQueue.objects.first()
    assert queued.process_parent_type == ProcessParentType.ACTIVATION
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
            orchestrator._manage_process_job_id(
                ProcessParentType.ACTIVATION, activation.id
            ),
            orchestrator._manage,
            ProcessParentType.ACTIVATION,
            activation.id,
        )
    ]
    for running in max_running_processes:
        call_args.append(
            mock.call(
                "activation",
                orchestrator._manage_process_job_id(
                    ProcessParentType.ACTIVATION, running.id
                ),
                orchestrator._manage,
                ProcessParentType.ACTIVATION,
                running.id,
            )
        )

    queue.push(
        ProcessParentType.ACTIVATION, activation.id, ActivationRequest.START
    )
    for running in max_running_processes:
        queue.push(
            ProcessParentType.ACTIVATION, running.id, ActivationRequest.START
        )
    orchestrator.monitor_rulebook_processes()

    enqueue_mock.assert_has_calls(call_args, any_order=True)


original_start_method = orchestrator.ActivationManager.start


@pytest.mark.django_db
@mock.patch.object(orchestrator.ActivationManager, "start", autospec=True)
def test_max_running_activation_after_start_job(
    start_mock,
    job_mock,
    activation,
    max_running_processes,
):
    """Check if the max running processes error is handled correctly
    when the limit is reached after the request is started."""

    def side_effect(*args, **kwargs):
        # Recreate the process and run the original start method
        instance = args[0]
        models.RulebookProcess.objects.create(
            name="running",
            activation=max_running_processes[0].activation,
            status=ActivationStatus.RUNNING,
        )
        original_start_method(instance, *args[1:], **kwargs)

    start_mock.side_effect = side_effect

    max_running_processes[0].delete()

    queue.push(
        ProcessParentType.ACTIVATION, activation.id, ActivationRequest.START
    )
    with mock.patch(
        "aap_eda.services.activation.activation_manager.get_current_job",
        return_value=job_mock,
    ):
        orchestrator._manage(ProcessParentType.ACTIVATION, activation.id)
    assert start_mock.call_count == 1
    running_processes = models.RulebookProcess.objects.filter(
        status__in=[ActivationStatus.STARTING, ActivationStatus.RUNNING]
    ).count()
    assert running_processes == settings.MAX_RUNNING_ACTIVATIONS
