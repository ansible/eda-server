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

import logging
from contextlib import contextmanager
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


def fake_task(number: int):
    pass


@pytest.fixture
def eda_caplog(caplog_factory):
    return caplog_factory(orchestrator.LOGGER, level=logging.DEBUG)


@pytest.fixture
def default_rulebook(
    default_organization: models.Organization,
) -> models.Rulebook:
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
        organization=default_organization,
    )


@pytest.fixture()
def activation(default_rulebook, default_organization):
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
        organization=default_organization,
    )
    return models.Activation.objects.create(
        name="test1",
        user=user,
        decision_environment=decision_environment,
        rulebook=default_rulebook,
        rulebook_rulesets=default_rulebook.rulesets,
        organization=default_organization,
    )


@pytest.fixture()
def bulk_running_processes(default_organization: models.Organization):
    count = 8
    user = models.User.objects.create_user(
        username="luke.skywalker2",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    processes = []
    for i in range(count):
        activation = models.Activation.objects.create(
            name=f"test_bulk_running{i}",
            user=user,
            organization=default_organization,
        )
        status = (
            ActivationStatus.STARTING if i == 0 else ActivationStatus.RUNNING
        )
        process = models.RulebookProcess.objects.create(
            name=f"running{i}",
            activation=activation,
            status=status,
            organization=default_organization,
        )
        processes.append(process)
        models.RulebookProcessQueue.objects.create(
            process=process,
            queue_name="activation",
        )
    return processes


@pytest.fixture
def job_mock():
    mock_job = mock.MagicMock()
    mock_job.origin = "activation"
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
@mock.patch("aap_eda.tasks.orchestrator.monitor_rulebook_processes")
@mock.patch("aap_eda.tasks.orchestrator.get_least_busy_queue_name")
def test_activation_requests(
    get_queue_name_mock,
    monitor_mock,
    activation,
    command,
    queued_request,
):
    get_queue_name_mock.return_value = "activation"
    command(ProcessParentType.ACTIVATION, activation.id)
    queued = models.ActivationRequestQueue.objects.first()
    assert queued.process_parent_type == ProcessParentType.ACTIVATION
    assert queued.process_parent_id == activation.id
    assert queued.request == queued_request
    assert monitor_mock.assert_called_once


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.tasking.unique_enqueue")
@mock.patch("aap_eda.tasks.orchestrator.get_least_busy_queue_name")
def test_monitor_rulebook_processes(
    get_queue_name_mock, enqueue_mock, activation, bulk_running_processes
):
    get_queue_name_mock.return_value = "activation"
    call_args = [
        mock.call(
            "activation",
            orchestrator._manage_process_job_id(
                ProcessParentType.ACTIVATION, activation.id
            ),
            orchestrator._manage,
            ProcessParentType.ACTIVATION,
            activation.id,
            "",
            timeout=settings.DISPATCHERD_ACTIVATION_TASK_TIMEOUT,
        )
    ]
    for running in bulk_running_processes:
        call_args.append(
            mock.call(
                "activation",
                orchestrator._manage_process_job_id(
                    ProcessParentType.ACTIVATION, running.activation.id
                ),
                orchestrator._manage,
                ProcessParentType.ACTIVATION,
                running.activation.id,
                "",
                timeout=settings.DISPATCHERD_ACTIVATION_TASK_TIMEOUT,
            )
        )

    queue.push(
        ProcessParentType.ACTIVATION, activation.id, ActivationRequest.START
    )
    for running in bulk_running_processes:
        queue.push(
            ProcessParentType.ACTIVATION,
            running.activation.id,
            ActivationRequest.START,
        )
    orchestrator.monitor_rulebook_processes()

    enqueue_mock.assert_has_calls(call_args, any_order=True)


original_start_method = orchestrator.ActivationManager.start


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.tasking.unique_enqueue")
def test_dispatch_existing_jobs(enqueue_mock, activation, eda_caplog):
    """Test that the dispatch does not process the request if there is
    already a job currently running."""
    job_id = orchestrator._manage_process_job_id(
        ProcessParentType.ACTIVATION, activation.id
    )
    activation.status = ActivationStatus.STOPPED
    activation.save(update_fields=["status"])

    @contextmanager
    def advisory_lock_mock(*args, **kwargs):
        yield False

    with mock.patch(
        "aap_eda.tasks.orchestrator.advisory_lock", advisory_lock_mock
    ):
        orchestrator.queue_dispatch(
            ProcessParentType.ACTIVATION,
            activation.id,
            ActivationRequest.START,
        )

        enqueue_mock.assert_not_called()
        assert f"_manage({job_id}) already being ran, " in eda_caplog.text
        activation.refresh_from_db()
        assert activation.status == ActivationStatus.STOPPED


#################################################################
# Health Check Tests - New coverage for check_rulebook_queue_health
#################################################################


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.get_control_from_settings")
def test_check_rulebook_queue_health_success(mock_get_control, eda_caplog):
    """Test successful health check returns True."""
    queue_name = "test_queue"

    # Mock healthy response
    mock_control = mock.Mock()
    mock_control.control_with_reply.return_value = {"status": "alive"}
    mock_get_control.return_value = mock_control

    result = orchestrator.check_rulebook_queue_health(queue_name)

    assert result is True
    mock_get_control.assert_called_once()
    mock_control.control_with_reply.assert_called_once_with(
        "alive", timeout=settings.DISPATCHERD_QUEUE_HEALTHCHECK_TIMEOUT
    )


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.get_control_from_settings")
def test_check_rulebook_queue_health_unhealthy(mock_get_control, eda_caplog):
    """Test unhealthy queue response logs warning and returns False."""
    queue_name = "test_queue"

    # Mock unhealthy response (None or falsy)
    mock_control = mock.Mock()
    mock_control.control_with_reply.return_value = None
    mock_get_control.return_value = mock_control

    result = orchestrator.check_rulebook_queue_health(queue_name)

    assert result is False
    assert (
        f"Worker queue {queue_name} was found to not be healthy"
        in eda_caplog.text
    )


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.get_control_from_settings")
def test_check_rulebook_queue_health_connection_failure(
    mock_get_control, eda_caplog
):
    """Test connection failure is handled gracefully."""
    queue_name = "test_queue"

    # Mock connection failure
    mock_get_control.side_effect = ConnectionError(
        "Failed to connect to dispatcherd"
    )

    result = orchestrator.check_rulebook_queue_health(queue_name)

    assert result is False
    assert f"Health check failed for queue {queue_name}" in eda_caplog.text
    assert "Failed to connect to dispatcherd" in eda_caplog.text


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.get_control_from_settings")
def test_check_rulebook_queue_health_timeout(mock_get_control, eda_caplog):
    """Test timeout during health check is handled."""
    queue_name = "test_queue"

    # Mock timeout
    mock_control = mock.Mock()
    mock_control.control_with_reply.side_effect = TimeoutError(
        "Health check timeout"
    )
    mock_get_control.return_value = mock_control

    result = orchestrator.check_rulebook_queue_health(queue_name)

    assert result is False
    assert f"Health check failed for queue {queue_name}" in eda_caplog.text
    assert "Health check timeout" in eda_caplog.text


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.get_control_from_settings")
def test_check_rulebook_queue_health_invalid_response(
    mock_get_control, eda_caplog
):
    """Test invalid response format is handled."""
    queue_name = "test_queue"

    # Mock invalid response format
    mock_control = mock.Mock()
    mock_control.control_with_reply.side_effect = ValueError(
        "Invalid response format"
    )
    mock_get_control.return_value = mock_control

    result = orchestrator.check_rulebook_queue_health(queue_name)

    assert result is False
    assert f"Health check failed for queue {queue_name}" in eda_caplog.text


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.get_control_from_settings")
@mock.patch("aap_eda.utils.sanitize_postgres_identifier")
def test_check_rulebook_queue_health_queue_name_sanitization(
    mock_sanitize, mock_get_control
):
    """Test that queue name is sanitized for PostgreSQL safety."""
    dangerous_queue_name = "queue'; DROP TABLE test; --"
    sanitized_name = "safe_queue"

    mock_sanitize.return_value = sanitized_name
    mock_control = mock.Mock()
    mock_control.control_with_reply.return_value = {"status": "alive"}
    mock_get_control.return_value = mock_control

    result = orchestrator.check_rulebook_queue_health(dangerous_queue_name)

    # Verify sanitization was called
    mock_sanitize.assert_called_once_with(dangerous_queue_name)

    # Verify sanitized name was used in control setup
    mock_get_control.assert_called_once_with(
        default_publish_channel=sanitized_name
    )

    assert result is True


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.get_control_from_settings")
def test_check_rulebook_queue_health_with_timeout_setting(mock_get_control):
    """Test that health check uses correct timeout setting."""
    queue_name = "test_queue"

    mock_control = mock.Mock()
    mock_control.control_with_reply.return_value = {"status": "alive"}
    mock_get_control.return_value = mock_control

    orchestrator.check_rulebook_queue_health(queue_name)

    # Verify timeout setting is used
    mock_control.control_with_reply.assert_called_once_with(
        "alive", timeout=settings.DISPATCHERD_QUEUE_HEALTHCHECK_TIMEOUT
    )


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.orchestrator.get_control_from_settings")
def test_check_rulebook_queue_health_falsy_response_types(
    mock_get_control, eda_caplog
):
    """Test various falsy response values are handled correctly."""
    queue_name = "test_queue"
    mock_control = mock.Mock()
    mock_get_control.return_value = mock_control

    # Test different falsy values
    falsy_values = [None, False, 0, "", [], {}]

    for falsy_value in falsy_values:
        eda_caplog.clear()
        mock_control.control_with_reply.return_value = falsy_value

        result = orchestrator.check_rulebook_queue_health(queue_name)

        assert result is False
        assert (
            f"Worker queue {queue_name} was found to not be healthy"
            in eda_caplog.text
        )
