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
"""Activation Manager tests."""
# TODO(alex) dedup code and fixtures across all the tests

from unittest.mock import MagicMock, create_autospec

import pytest
from _pytest.logging import LogCaptureFixture
from django.conf import settings as django_settings
from django.utils import timezone
from pytest_django.fixtures import SettingsWrapper
from pytest_lazyfixture import lazy_fixture

from aap_eda.core import enums, models
from aap_eda.services.activation.activation_manager import (
    LOGGER,
    ActivationManager,
    exceptions,
)
from aap_eda.services.activation.engine import exceptions as engine_exceptions
from aap_eda.services.activation.engine.common import (
    ContainerEngine,
    ContainerRequest,
)
from aap_eda.services.activation.status_manager import StatusManager


def apply_settings(settings: SettingsWrapper, **kwargs):
    """Apply settings."""
    for key, value in kwargs.items():
        setattr(settings, key, value)


@pytest.fixture
def rulebook_with_job_template(
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
        run_job_template:
          msg: "Hello World!"

"""
    return models.Rulebook.objects.create(
        name="test-rulebook",
        rulesets=rulesets,
        organization=default_organization,
    )


@pytest.fixture
def eda_caplog(caplog_factory) -> LogCaptureFixture:
    """Fixture to capture logs from the EDA logger."""
    return caplog_factory(LOGGER)


@pytest.fixture
def activation_with_instance(
    default_organization: models.Organization,
    basic_activation: models.Activation,
) -> models.Activation:
    """Return an activation with an instance."""
    models.RulebookProcess.objects.create(
        activation=basic_activation,
        organization=default_organization,
    )
    return basic_activation


@pytest.fixture
def starting_activation(activation_with_instance: models.Activation):
    """Return a running activation."""
    activation = activation_with_instance
    activation.status = enums.ActivationStatus.STARTING
    activation.save(update_fields=["status"])
    activation.latest_instance.status = enums.ActivationStatus.STARTING
    activation.latest_instance.activation_pod_id = "test-pod-id"
    activation.latest_instance.updated_at = timezone.now()
    activation.latest_instance.save(
        update_fields=["status", "activation_pod_id", "updated_at"],
    )
    return activation


@pytest.fixture
def running_activation(activation_with_instance: models.Activation):
    """Return a running activation."""
    activation = activation_with_instance
    activation.status = enums.ActivationStatus.RUNNING
    activation.save(update_fields=["status"])
    activation.latest_instance.status = enums.ActivationStatus.RUNNING
    activation.latest_instance.activation_pod_id = "test-pod-id"
    activation.latest_instance.save(
        update_fields=["status", "activation_pod_id"],
    )
    return activation


@pytest.fixture
def basic_activation(
    default_user: models.User,
    default_decision_environment: models.DecisionEnvironment,
    default_rulebook: models.Rulebook,
    default_organization: models.Organization,
) -> models.Activation:
    """Return the minimal activation."""
    return models.Activation.objects.create(
        name="test-activation",
        user=default_user,
        decision_environment=default_decision_environment,
        rulebook=default_rulebook,
        # rulebook_rulesets is populated by the serializer
        rulebook_rulesets=default_rulebook.rulesets,
        log_level=enums.RulebookProcessLogLevel.INFO,
        organization=default_organization,
    )


@pytest.fixture
def new_activation_with_instance(
    default_user: models.User,
    default_decision_environment: models.DecisionEnvironment,
    default_rulebook: models.Rulebook,
    default_organization: models.Organization,
) -> models.Activation:
    """Return an activation with an instance."""
    activation = models.Activation.objects.create(
        name="new_activation_with_instance",
        user=default_user,
        decision_environment=default_decision_environment,
        rulebook=default_rulebook,
        # rulebook_rulesets is populated by the serializer
        rulebook_rulesets=default_rulebook.rulesets,
        organization=default_organization,
    )
    models.RulebookProcess.objects.create(
        activation=activation,
        status=enums.ActivationStatus.RUNNING,
        organization=default_organization,
    )
    models.RulebookProcessQueue.objects.create(
        process=activation.latest_instance,
        queue_name="queue_name_test",
    )
    return activation


@pytest.fixture
def container_engine_mock() -> MagicMock:
    return create_autospec(ContainerEngine, instance=True)


@pytest.fixture
def job_mock():
    mock_job = MagicMock()
    mock_job.origin = "queue_name_test"
    return mock_job


@pytest.fixture
def running_container_status_mock():
    status_mock = MagicMock()
    status_mock.status = enums.ActivationStatus.RUNNING
    return status_mock


@pytest.mark.django_db
def test_get_container_request(
    activation_with_instance: models.Activation,
    settings: SettingsWrapper,
    container_engine_mock: MagicMock,
):
    """Test build_cmdline."""
    override_settings = {
        "WEBSOCKET_BASE_URL": "ws://localhost:8000",
        "WEBSOCKET_SSL_VERIFY": "no",
        "RULEBOOK_LIVENESS_CHECK_SECONDS": 73,
    }
    apply_settings(settings, **override_settings)
    activation_manager = ActivationManager(
        activation_with_instance,
        container_engine=container_engine_mock,
    )
    request = activation_manager._get_container_request()
    assert isinstance(request, ContainerRequest)
    cmdline = request.cmdline
    assert cmdline.ws_url.startswith(override_settings["WEBSOCKET_BASE_URL"])
    assert cmdline.log_level == "-v"
    assert cmdline.ws_ssl_verify == override_settings["WEBSOCKET_SSL_VERIFY"]
    assert (
        cmdline.heartbeat
        == override_settings["RULEBOOK_LIVENESS_CHECK_SECONDS"]
    )
    assert cmdline.id == str(activation_with_instance.latest_instance.id)


@pytest.mark.django_db
def test_get_container_request_no_instance(
    basic_activation, container_engine_mock
):
    """Test build_cmdline when no instance exists."""
    activation_manager = ActivationManager(
        basic_activation, container_engine_mock
    )
    with pytest.raises(exceptions.ActivationManagerError):
        activation_manager._get_container_request()


@pytest.mark.django_db
def test_start_deleted_activation(
    activation_with_instance, container_engine_mock
):
    """Test start verb when activation is deleted."""
    activation_manager = ActivationManager(
        activation_with_instance, container_engine_mock
    )
    activation_with_instance.delete()
    with pytest.raises(exceptions.ActivationStartError) as exc:
        activation_manager.start()
    assert "does not exist" in str(exc.value)


@pytest.mark.django_db
def test_start_disabled_activation(
    activation_with_instance, eda_caplog, container_engine_mock
):
    """Test start verb when activation is deleted."""
    err_msg = "is disabled. Can not be started."
    activation_manager = ActivationManager(
        activation_with_instance, container_engine_mock
    )
    activation_with_instance.is_enabled = False
    activation_with_instance.save(update_fields=["is_enabled"])
    with pytest.raises(exceptions.ActivationStartError) as exc:
        activation_manager.start()
    assert err_msg in eda_caplog.text
    assert err_msg in str(exc.value)


@pytest.mark.django_db
def test_start_no_awx_token(
    basic_activation,
    rulebook_with_job_template,
    container_engine_mock,
    preseed_credential_types,
):
    """Test start verb when no AWX token is present."""
    basic_activation.rulebook = rulebook_with_job_template
    basic_activation.save(update_fields=["rulebook"])
    activation_manager = ActivationManager(
        basic_activation, container_engine_mock
    )
    basic_activation.user.awxtoken_set.all().delete()
    with pytest.raises(exceptions.ActivationStartError) as exc:
        activation_manager.start()
    assert basic_activation.status == enums.ActivationStatus.ERROR
    assert "The rulebook requires a RH AAP credential." in str(exc.value)
    assert str(exc.value) in basic_activation.status_message


@pytest.mark.django_db
def test_start_no_decision_environment(
    basic_activation, container_engine_mock
):
    """Test start verb when no decision environment is present."""
    activation_manager = ActivationManager(
        basic_activation, container_engine_mock
    )
    basic_activation.decision_environment.delete()
    with pytest.raises(exceptions.ActivationStartError) as exc:
        activation_manager.start()
    assert basic_activation.status == enums.ActivationStatus.ERROR
    assert "decision_environment" in str(exc.value)
    assert "Decision Environment is needed" in str(exc.value)
    assert str(exc.value) in basic_activation.status_message


@pytest.mark.django_db
def test_start_already_running(
    running_activation: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
    preseed_credential_types,
):
    """Test start verb when activation is already running."""
    activation_manager = ActivationManager(
        db_instance=running_activation,
        container_engine=container_engine_mock,
    )
    container_engine_mock.get_status.return_value = MagicMock(
        status=enums.ActivationStatus.RUNNING,
    )

    activation_manager.start()
    assert container_engine_mock.get_status.called
    assert "already running" in eda_caplog.text
    assert running_activation.status == enums.ActivationStatus.RUNNING


@pytest.mark.django_db
def test_start_first_run(
    basic_activation: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
    preseed_credential_types,
):
    """Test start verb for a new activation."""
    activation_manager = ActivationManager(
        db_instance=basic_activation,
        container_engine=container_engine_mock,
    )
    container_engine_mock.start.return_value = "test-pod-id"
    activation_manager.start()
    assert container_engine_mock.start.called
    assert container_engine_mock.update_logs.called
    assert "Starting" in eda_caplog.text
    assert basic_activation.status == enums.ActivationStatus.STARTING
    assert (
        basic_activation.latest_instance.status
        == enums.ActivationStatus.STARTING
    )
    assert basic_activation.latest_instance.activation_pod_id == "test-pod-id"
    assert basic_activation.restart_count == 0

    rulebook_process_queue = models.RulebookProcessQueue.objects.get(
        process=basic_activation.latest_instance,
    )
    assert (
        rulebook_process_queue.queue_name
        == django_settings.RULEBOOK_QUEUE_NAME
    )

    logs = models.RulebookProcessLog.objects.filter(
        activation_instance=basic_activation.latest_instance
    ).all()
    assert not any("The activation was edited at" in log.log for log in logs)


@pytest.mark.django_db
def test_monitor_to_running_status(
    starting_activation: models.Activation,
    container_engine_mock: MagicMock,
    running_container_status_mock: MagicMock,
):
    """Teset monitor task brings activation to running status"""
    activation_manager = ActivationManager(
        db_instance=starting_activation,
        container_engine=container_engine_mock,
    )
    container_engine_mock.get_status.return_value = (
        running_container_status_mock
    )
    activation_manager.monitor()
    assert starting_activation.status == enums.ActivationStatus.RUNNING
    assert (
        starting_activation.latest_instance.status
        == enums.ActivationStatus.RUNNING
    )
    assert starting_activation.restart_count == 0


@pytest.mark.django_db
def test_monitor_to_unexpected_error_status(
    running_activation: models.Activation,
    container_engine_mock: MagicMock,
):
    """Test monitor when get_status returns an unexpected error."""
    activation_manager = ActivationManager(
        db_instance=running_activation,
        container_engine=container_engine_mock,
    )
    container_engine_mock.get_status.side_effect = (
        engine_exceptions.ContainerEngineError("unexpected error")
    )
    with pytest.raises(exceptions.ActivationMonitorError):
        activation_manager.monitor()
    assert running_activation.status == enums.ActivationStatus.ERROR
    assert "unexpected error" in running_activation.status_message


@pytest.mark.django_db
def test_monitor_container_not_found(
    running_activation: models.Activation,
    container_engine_mock: MagicMock,
):
    """Test monitor when get_status returns a container not found error."""
    activation_manager = ActivationManager(
        db_instance=running_activation,
        container_engine=container_engine_mock,
    )
    container_engine_mock.get_status.side_effect = (
        engine_exceptions.ContainerNotFoundError("Not found")
    )
    activation_manager.monitor()
    assert running_activation.status == enums.ActivationStatus.FAILED


@pytest.mark.django_db
def test_start_restart(
    running_activation: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
    preseed_credential_types,
):
    """Test start verb for a restarted activation."""
    running_activation.edited_at = timezone.now()
    running_activation.save(update_fields=["edited_at"])
    activation_manager = ActivationManager(
        db_instance=running_activation,
        container_engine=container_engine_mock,
    )
    container_engine_mock.start.return_value = "test-pod-id"
    activation_manager.start(is_restart=True)
    assert container_engine_mock.start.called
    assert container_engine_mock.update_logs.called
    assert "Starting" in eda_caplog.text
    assert running_activation.status == enums.ActivationStatus.STARTING
    assert (
        running_activation.latest_instance.status
        == enums.ActivationStatus.STARTING
    )
    assert (
        running_activation.latest_instance.activation_pod_id == "test-pod-id"
    )
    assert running_activation.restart_count == 1
    rulebook_process_queue = models.RulebookProcessQueue.objects.get(
        process=running_activation.latest_instance,
    )
    assert (
        rulebook_process_queue.queue_name
        == django_settings.RULEBOOK_QUEUE_NAME
    )
    logs = models.RulebookProcessLog.objects.filter(
        activation_instance=running_activation.latest_instance
    ).all()
    assert any("The activation was edited at" in log.log for log in logs)


@pytest.mark.django_db
def test_stop_deleted_activation(
    activation_with_instance: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
):
    """Test stop verb when activation is deleted."""
    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=activation_with_instance,
    )
    activation_with_instance.delete()
    with pytest.raises(exceptions.ActivationStopError) as exc:
        activation_manager.stop()
    assert "Stopping" in eda_caplog.text
    assert "does not exist" in str(exc.value)
    assert "does not exist" in eda_caplog.text


@pytest.mark.parametrize(
    ("end_status", "expected"),
    [
        (enums.ActivationStatus.ERROR, True),
        (enums.ActivationStatus.STOPPED, True),
        (enums.ActivationStatus.FAILED, True),
        (enums.ActivationStatus.COMPLETED, True),
        (enums.ActivationStatus.PENDING, False),
        (enums.ActivationStatus.STARTING, False),
        (enums.ActivationStatus.RUNNING, False),
    ],
)
@pytest.mark.django_db
def test_stop_already_stopped(
    activation_with_instance: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
    end_status: enums.ActivationStatus,
    expected: bool,
):
    """Test stop verb when activation is stopped."""
    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=activation_with_instance,
    )

    activation_with_instance.status = end_status
    activation_with_instance.latest_instance.status = end_status
    activation_with_instance.latest_instance.save(
        update_fields=["status"],
    )
    activation_with_instance.save(update_fields=["status"])

    activation_manager.stop(disable=True)
    assert "Stopping" in eda_caplog.text
    stopped = "already stopped" in eda_caplog.text
    assert stopped == expected
    assert not container_engine_mock.cleanup.called


@pytest.mark.parametrize(
    ("before_status", "after_status", "before_msg", "after_msg"),
    [
        (
            enums.ActivationStatus.RUNNING,
            enums.ActivationStatus.STOPPED,
            "running",
            "Stop requested by user.",
        ),
        (
            enums.ActivationStatus.ERROR,
            enums.ActivationStatus.ERROR,
            "activation validation failed",
            "activation validation failed",
        ),
    ],
)
@pytest.mark.django_db
def test_stop_running(
    running_activation: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
    before_status,
    after_status,
    before_msg,
    after_msg,
):
    """Test stop verb when activation is running."""
    running_activation.status = before_status
    running_activation.status_message = before_msg
    running_activation.save(update_fields=["status", "status_message"])
    running_activation.latest_instance.status = before_status
    running_activation.latest_instance.save(update_fields=["status"])
    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=running_activation,
    )
    container_engine_mock.get_status.return_value = None

    activation_manager.stop()
    assert "Stopping" in eda_caplog.text
    assert running_activation.status == after_status
    assert running_activation.latest_instance.status == after_status
    assert running_activation.status_message == after_msg

    if before_status == enums.ActivationStatus.RUNNING:
        assert "Cleanup operation requested" in eda_caplog.text
        assert "Activation stopped." in eda_caplog.text
        assert running_activation.latest_instance.activation_pod_id is None
        assert container_engine_mock.cleanup.called


@pytest.mark.django_db
def test_stop_no_pod(
    running_activation: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
):
    """Test stop verb when activation is running but no pod is found."""
    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=running_activation,
    )

    container_engine_mock.get_status.side_effect = (
        engine_exceptions.ContainerNotFoundError
    )

    activation_manager.stop()
    assert "Stopping" in eda_caplog.text
    assert "Cleanup operation requested" in eda_caplog.text
    assert "Activation stopped." in eda_caplog.text
    assert running_activation.status == enums.ActivationStatus.STOPPED
    assert (
        running_activation.latest_instance.status
        == enums.ActivationStatus.STOPPED
    )
    assert running_activation.latest_instance.activation_pod_id is None
    assert running_activation.status_message == "Stop requested by user."
    assert container_engine_mock.cleanup.called


@pytest.mark.django_db
def test_stop_pending(
    basic_activation: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
):
    """Test stop verb when activation is pending."""
    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=basic_activation,
    )

    activation_manager.stop()
    assert "Stopping" in eda_caplog.text
    assert not container_engine_mock.get_status.called
    assert not container_engine_mock.cleanup.called
    assert "No instance found" in eda_caplog.text
    assert basic_activation.status == enums.ActivationStatus.STOPPED
    assert basic_activation.latest_instance is None


@pytest.mark.django_db
def test_stop_stopped_instance_running(
    running_activation: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
):
    """Test stop verb when activation is stopped but instance is running."""
    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=running_activation,
    )

    running_activation.status = enums.ActivationStatus.STOPPED
    running_activation.save(update_fields=["status"])

    activation_manager.stop()
    assert "Stopping" in eda_caplog.text
    assert container_engine_mock.get_status.called
    assert container_engine_mock.cleanup.called
    assert running_activation.status == enums.ActivationStatus.STOPPED
    assert (
        running_activation.latest_instance.status
        == enums.ActivationStatus.STOPPED
    )
    assert running_activation.latest_instance.activation_pod_id is None


@pytest.mark.django_db
def test_stop_stopped_pod_running(
    running_activation: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
):
    """Test stop verb when activation is stopped but pod is running."""
    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=running_activation,
    )

    running_activation.status = enums.ActivationStatus.STOPPED
    running_activation.save(update_fields=["status"])
    running_activation.latest_instance.status = enums.ActivationStatus.STOPPED
    running_activation.latest_instance.save(update_fields=["status"])

    container_engine_mock.get_status.return_value = MagicMock(
        status=enums.ActivationStatus.RUNNING,
    )

    activation_manager.stop()
    assert "Stopping" in eda_caplog.text
    assert container_engine_mock.get_status.called
    assert container_engine_mock.cleanup.called
    assert running_activation.status == enums.ActivationStatus.STOPPED
    assert (
        running_activation.latest_instance.status
        == enums.ActivationStatus.STOPPED
    )
    assert running_activation.latest_instance.activation_pod_id is None


@pytest.mark.django_db
def test_delete_already_deleted(
    activation_with_instance: models.Activation,
    eda_caplog: LogCaptureFixture,
):
    """Test delete verb when activation is deleted."""
    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=activation_with_instance,
    )
    activation_with_instance.delete()
    with pytest.raises(exceptions.ActivationManagerError) as exc:
        activation_manager.delete()
    assert "Delete operation requested" in eda_caplog.text
    assert "does not exist" in str(exc.value)
    assert "does not exist" in eda_caplog.text


@pytest.mark.parametrize(
    "activation,status",
    [
        pytest.param(
            lazy_fixture("activation_with_instance"),
            enums.ActivationStatus.STOPPED,
            id="stopped",
        ),
        pytest.param(
            lazy_fixture("activation_with_instance"),
            enums.ActivationStatus.ERROR,
            id="error",
        ),
        pytest.param(
            lazy_fixture("activation_with_instance"),
            enums.ActivationStatus.FAILED,
            id="failed",
        ),
        pytest.param(
            lazy_fixture("activation_with_instance"),
            enums.ActivationStatus.COMPLETED,
            id="completed",
        ),
    ],
)
@pytest.mark.django_db
def test_delete_no_pod(
    activation: models.Activation,
    status: enums.ActivationStatus,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
):
    """Test delete verb for any activation."""
    activation.status = status
    activation.save(update_fields=["status"])
    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=activation,
    )

    activation_manager.delete()
    assert "Delete operation requested" in eda_caplog.text
    assert "Cleanup operation requested" in eda_caplog.text
    assert "Activation deleted." in eda_caplog.text
    assert not container_engine_mock.cleanup.called
    assert models.Activation.objects.filter(id=activation.id).count() == 0


@pytest.mark.django_db
def test_delete_running(
    running_activation: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
):
    """Test delete verb when activation is running."""
    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=running_activation,
    )

    activation_manager.delete()
    assert "Delete operation requested" in eda_caplog.text
    assert "Cleanup operation requested" in eda_caplog.text
    assert "Activation deleted." in eda_caplog.text
    assert container_engine_mock.cleanup.called
    assert (
        models.Activation.objects.filter(id=running_activation.id).count() == 0
    )


@pytest.mark.django_db
def test_delete_with_exception(
    running_activation: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
):
    """Test that the activation is deleted even if there is an error."""
    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=running_activation,
    )
    container_engine_mock.cleanup.side_effect = Exception("test")
    activation_manager.delete()
    assert container_engine_mock.cleanup.called
    assert "Delete operation requested" in eda_caplog.text
    assert "failed to clean up." in eda_caplog.text
    assert (
        models.Activation.objects.filter(id=running_activation.id).count() == 0
    )


@pytest.mark.django_db
def test_start_max_running_activations(
    basic_activation: models.Activation,
    new_activation_with_instance: models.Activation,
    settings: SettingsWrapper,
    eda_caplog: LogCaptureFixture,
    container_engine_mock: MagicMock,
    preseed_credential_types,
):
    """Test start verb when max running activations is reached."""
    apply_settings(settings, MAX_RUNNING_ACTIVATIONS=1)
    apply_settings(settings, RULEBOOK_QUEUE_NAME="queue_name_test")
    activation_manager = ActivationManager(
        basic_activation, container_engine_mock
    )
    with pytest.raises(exceptions.MaxRunningProcessesError):
        activation_manager.start()
    assert "No capacity to start a new rulebook process" in eda_caplog.text


@pytest.mark.django_db
def test_init_status_manager_with_activation(basic_activation):
    status_manager = StatusManager(basic_activation)
    assert status_manager.db_instance == basic_activation
    assert status_manager.latest_instance == basic_activation.latest_instance
    assert (
        status_manager.db_instance_type == enums.ProcessParentType.ACTIVATION
    )


@pytest.mark.parametrize(
    "process_parent",
    [
        pytest.param(
            lazy_fixture("new_activation_with_instance"),
        ),
    ],
)
@pytest.mark.django_db
def test_status_manager_set_latest_instance_status(process_parent):
    status_manager = StatusManager(process_parent)
    status_manager.set_latest_instance_status(
        status=enums.ActivationStatus.PENDING,
        status_message="Instance is pending",
    )
    assert (
        process_parent.latest_instance.status == enums.ActivationStatus.PENDING
    )
    assert (
        process_parent.latest_instance.status_message == "Instance is pending"
    )


@pytest.mark.parametrize(
    "process_parent",
    [
        pytest.param(
            lazy_fixture("new_activation_with_instance"),
        ),
    ],
)
@pytest.mark.django_db
def test_status_manager_set_status(process_parent):
    status_manager = StatusManager(process_parent)
    status_manager.set_status(
        status=enums.ActivationStatus.PENDING,
        status_message="Activation is pending",
    )
    assert process_parent.status == enums.ActivationStatus.PENDING
    assert process_parent.status_message == "Activation is pending"
