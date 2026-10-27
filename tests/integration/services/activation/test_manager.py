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

from unittest.mock import MagicMock, create_autospec, patch

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
from aap_eda.services.activation.engine.kubernetes import (
    Engine as KubernetesEngine,
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
        name=basic_activation.name,
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
        name=activation.name,
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


@pytest.fixture
def failing_cleanup(container_engine_mock):
    container_engine_mock.cleanup.side_effect = (
        engine_exceptions.ContainerCleanupError("cleanup failed")
    )
    return container_engine_mock


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
    assert not any("Job started in namespace" in log.log for log in logs)


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
def test_monitor_preserves_failure_count_on_running_transition(
    starting_activation: models.Activation,
    container_engine_mock: MagicMock,
    running_container_status_mock: MagicMock,
):
    """AAP-78375: failure_count must not reset on STARTING->RUNNING."""
    starting_activation.failure_count = 3
    starting_activation.save(update_fields=["failure_count"])

    activation_manager = ActivationManager(
        db_instance=starting_activation,
        container_engine=container_engine_mock,
    )
    container_engine_mock.get_status.return_value = (
        running_container_status_mock
    )
    activation_manager.monitor()

    starting_activation.refresh_from_db()
    assert starting_activation.status == enums.ActivationStatus.RUNNING
    assert starting_activation.failure_count == 3


@pytest.mark.django_db
def test_monitor_container_engine_error_sets_workers_offline(
    running_activation: models.Activation,
    container_engine_mock: MagicMock,
):
    """Test monitor sets WORKERS_OFFLINE on transient ContainerEngineError.

    When the K8s API is temporarily unreachable the activation should
    transition to WORKERS_OFFLINE (recoverable) instead of ERROR
    (terminal), so the monitor loop can retry on the next cycle.
    """
    activation_manager = ActivationManager(
        db_instance=running_activation,
        container_engine=container_engine_mock,
    )
    container_engine_mock.get_status.side_effect = (
        engine_exceptions.ContainerEngineError("unexpected error")
    )
    activation_manager.monitor()
    assert running_activation.status == enums.ActivationStatus.WORKERS_OFFLINE
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


@pytest.mark.parametrize(
    "container_status",
    [
        enums.ActivationStatus.COMPLETED,
        enums.ActivationStatus.FAILED,
        enums.ActivationStatus.ERROR,
    ],
)
@pytest.mark.django_db
def test_monitor_cleanup_failure_preserves_job_for_retry(
    running_activation: models.Activation,
    container_status: enums.ActivationStatus,
):
    """Do not apply terminal policies when Job deletion is uncertain."""
    engine = MagicMock(spec=KubernetesEngine)
    engine.namespace = "new-ns"
    engine.get_status.return_value = MagicMock(
        status=container_status, message="container exited"
    )
    engine.cleanup.side_effect = engine_exceptions.ContainerCleanupError(
        "cleanup failed"
    )
    process = running_activation.latest_instance
    process.activation_job_namespace = "old-ns"
    process.save(update_fields=["activation_job_namespace"])
    manager = ActivationManager(running_activation, container_engine=engine)

    with patch(SYSTEM_RESTART_PATH) as restart_mock:
        with pytest.raises(exceptions.ActivationMonitorError) as exc:
            manager.monitor()

    assert isinstance(
        exc.value.__cause__, engine_exceptions.ContainerCleanupError
    )
    running_activation.refresh_from_db()
    process.refresh_from_db()
    assert running_activation.status == enums.ActivationStatus.RUNNING
    if container_status == enums.ActivationStatus.ERROR:
        assert process.status == enums.ActivationStatus.RUNNING
    else:
        assert process.status == container_status
    assert process.activation_pod_id == "test-pod-id"
    assert engine.namespace == "new-ns"
    engine.cleanup.assert_called_once()
    restart_mock.assert_not_called()


@pytest.mark.parametrize(
    ("container_status", "should_restart"),
    [
        (enums.ActivationStatus.COMPLETED, False),
        (enums.ActivationStatus.FAILED, True),
    ],
)
@pytest.mark.django_db
def test_monitor_retries_terminal_cleanup_before_applying_policy(
    running_activation: models.Activation,
    container_status: enums.ActivationStatus,
    should_restart: bool,
):
    """Keep the observed terminal result while cleanup verification retries."""
    running_activation.restart_policy = enums.RestartPolicy.ON_FAILURE
    running_activation.save(update_fields=["restart_policy"])
    engine = MagicMock(spec=KubernetesEngine)
    engine.namespace = "new-ns"
    engine.get_status.return_value = MagicMock(
        status=container_status, message="container exited"
    )
    engine.cleanup.side_effect = [
        engine_exceptions.ContainerCleanupError("verification unavailable"),
        None,
    ]
    process = running_activation.latest_instance
    process.activation_job_namespace = "old-ns"
    process.save(update_fields=["activation_job_namespace"])
    manager = ActivationManager(running_activation, container_engine=engine)

    with patch(SYSTEM_RESTART_PATH) as restart_mock:
        with pytest.raises(exceptions.ActivationMonitorError):
            manager.monitor()

        running_activation.refresh_from_db()
        process.refresh_from_db()
        assert running_activation.status == enums.ActivationStatus.RUNNING
        assert process.status == container_status
        assert process.activation_pod_id == "test-pod-id"

        manager.monitor()

    running_activation.refresh_from_db()
    process.refresh_from_db()
    assert running_activation.status == container_status
    assert process.status == container_status
    assert engine.cleanup.call_count == 2
    assert engine.get_status.call_count == 1
    if should_restart:
        restart_mock.assert_called_once()
    else:
        restart_mock.assert_not_called()


@pytest.mark.parametrize(
    "container_status",
    [
        enums.ActivationStatus.COMPLETED,
        enums.ActivationStatus.FAILED,
    ],
)
@pytest.mark.django_db
def test_monitor_preserves_terminal_status_while_cleanup_retries(
    running_activation: models.Activation,
    container_status: enums.ActivationStatus,
):
    """Do not replace a terminal result during a cleanup retry outage."""
    running_activation.restart_policy = enums.RestartPolicy.NEVER
    running_activation.save(update_fields=["restart_policy"])
    engine = MagicMock(spec=KubernetesEngine)
    engine.namespace = "new-ns"
    engine.get_status.return_value = MagicMock(
        status=container_status, message="container exited"
    )
    engine.cleanup.side_effect = [
        engine_exceptions.ContainerCleanupError("verification unavailable"),
        engine_exceptions.ContainerCleanupError("API unavailable"),
        None,
    ]
    process = running_activation.latest_instance
    process.activation_job_namespace = "old-ns"
    process.save(update_fields=["activation_job_namespace"])
    manager = ActivationManager(running_activation, container_engine=engine)

    with pytest.raises(exceptions.ActivationMonitorError):
        manager.monitor()

    with pytest.raises(exceptions.ActivationMonitorError):
        manager.monitor()

    running_activation.refresh_from_db()
    process.refresh_from_db()
    assert running_activation.status == enums.ActivationStatus.RUNNING
    assert process.status == container_status
    assert process.activation_pod_id == "test-pod-id"
    assert engine.get_status.call_count == 1

    manager.monitor()

    running_activation.refresh_from_db()
    process.refresh_from_db()
    assert running_activation.status == container_status
    assert process.status == container_status
    assert engine.cleanup.call_count == 3


@pytest.mark.parametrize(
    "container_status",
    [
        enums.ActivationStatus.COMPLETED,
        enums.ActivationStatus.FAILED,
        enums.ActivationStatus.ERROR,
    ],
)
@pytest.mark.django_db
def test_monitor_terminal_status_after_cleanup(
    running_activation: models.Activation,
    container_status: enums.ActivationStatus,
):
    """Successful cleanup still applies the corresponding terminal policy."""
    running_activation.restart_policy = enums.RestartPolicy.NEVER
    running_activation.save(update_fields=["restart_policy"])
    engine = MagicMock(spec=KubernetesEngine)
    engine.namespace = "new-ns"
    engine.get_status.return_value = MagicMock(
        status=container_status, message="container exited"
    )
    process = running_activation.latest_instance
    process.activation_job_namespace = "new-ns"
    process.save(update_fields=["activation_job_namespace"])
    manager = ActivationManager(running_activation, container_engine=engine)

    if container_status == enums.ActivationStatus.ERROR:
        with pytest.raises(exceptions.ActivationMonitorError):
            manager.monitor()
    else:
        manager.monitor()

    running_activation.refresh_from_db()
    assert running_activation.status == container_status
    assert running_activation.latest_instance.status == container_status
    engine.cleanup.assert_called_once()


@pytest.mark.parametrize(
    ("failure_count", "should_restart"),
    [
        (0, True),
        (django_settings.ACTIVATION_MAX_RESTARTS_ON_FAILURE, False),
    ],
)
@pytest.mark.django_db
def test_monitor_failed_job_cleans_up_once_with_restart_policy(
    running_activation: models.Activation,
    failure_count: int,
    should_restart: bool,
):
    """Failed Jobs are not cleaned up again when applying restart policy."""
    running_activation.restart_policy = enums.RestartPolicy.ON_FAILURE
    running_activation.failure_count = failure_count
    running_activation.save(update_fields=["restart_policy", "failure_count"])
    engine = MagicMock(spec=KubernetesEngine)
    engine.namespace = "new-ns"
    engine.get_status.return_value = MagicMock(
        status=enums.ActivationStatus.FAILED, message="container exited"
    )
    process = running_activation.latest_instance
    process.activation_job_namespace = "new-ns"
    process.save(update_fields=["activation_job_namespace"])
    manager = ActivationManager(running_activation, container_engine=engine)

    with patch(SYSTEM_RESTART_PATH) as restart_mock:
        manager.monitor()

    running_activation.refresh_from_db()
    process = running_activation.latest_instance
    process.refresh_from_db()
    assert running_activation.status == enums.ActivationStatus.FAILED
    assert process.status == enums.ActivationStatus.FAILED
    assert process.activation_pod_id is None
    assert running_activation.failure_count == failure_count + 1
    engine.cleanup.assert_called_once()
    if should_restart:
        restart_delay = django_settings.ACTIVATION_RESTART_SECONDS_ON_FAILURE
        restart_mock.assert_called_once_with(
            enums.ProcessParentType.ACTIVATION,
            running_activation.id,
            delay_seconds=restart_delay,
        )
    else:
        restart_mock.assert_not_called()


@pytest.mark.django_db
def test_error_instance_cleans_up_job_when_not_already_done(
    running_activation: models.Activation,
):
    """Errors with a live Job clean up in the recorded namespace."""
    process = running_activation.latest_instance
    process.activation_job_namespace = "old-ns"
    process.save(update_fields=["activation_job_namespace"])
    engine = MagicMock(spec=KubernetesEngine)
    engine.namespace = "new-ns"
    namespaces = []
    engine.cleanup.side_effect = lambda *_: namespaces.append(engine.namespace)
    manager = ActivationManager(running_activation, container_engine=engine)

    manager._error_instance("engine error")

    process.refresh_from_db()
    assert process.status == enums.ActivationStatus.ERROR
    assert process.activation_pod_id is None
    assert namespaces == ["old-ns"]
    assert engine.namespace == "new-ns"
    engine.cleanup.assert_called_once()
    assert engine.cleanup.call_args.args[0] == "test-pod-id"


@pytest.mark.django_db
def test_monitor_disabled_cleanup_failure_retries_until_stopped(
    running_activation: models.Activation,
):
    """Disabled, stopping activations retry cleanup until Job removal."""
    running_activation.is_enabled = False
    running_activation.status = enums.ActivationStatus.STOPPING
    running_activation.save(update_fields=["is_enabled", "status"])
    engine = MagicMock(spec=KubernetesEngine)
    engine.namespace = "new-ns"
    engine.cleanup.side_effect = engine_exceptions.ContainerCleanupError(
        "cleanup failed"
    )
    process = running_activation.latest_instance
    process.activation_job_namespace = "old-ns"
    process.save(update_fields=["activation_job_namespace"])
    manager = ActivationManager(running_activation, container_engine=engine)

    with pytest.raises(exceptions.ActivationMonitorError) as exc:
        manager.monitor()

    assert isinstance(exc.value.__cause__, exceptions.ActivationStopError)
    running_activation.refresh_from_db()
    assert running_activation.status == enums.ActivationStatus.STOPPING
    assert (
        running_activation.latest_instance.status
        == enums.ActivationStatus.RUNNING
    )
    assert (
        running_activation.latest_instance.activation_pod_id == "test-pod-id"
    )

    engine.cleanup.side_effect = None
    manager.monitor()

    running_activation.refresh_from_db()
    assert running_activation.status == enums.ActivationStatus.STOPPED
    assert (
        running_activation.latest_instance.status
        == enums.ActivationStatus.STOPPED
    )
    assert running_activation.latest_instance.activation_pod_id is None
    assert engine.cleanup.call_count == 2


@pytest.mark.django_db
def test_start_cleanup_failure_blocks_replacement(
    running_activation: models.Activation,
    preseed_credential_types,
):
    running_activation.status = enums.ActivationStatus.STOPPED
    running_activation.save(update_fields=["status"])
    engine = MagicMock(spec=KubernetesEngine)
    engine.namespace = "new-ns"
    engine.get_status.return_value = MagicMock(
        status=enums.ActivationStatus.STOPPED
    )
    engine.cleanup.side_effect = engine_exceptions.ContainerCleanupError(
        "cleanup failed"
    )
    process = running_activation.latest_instance
    process.activation_job_namespace = "old-ns"
    process.save(update_fields=["activation_job_namespace"])
    manager = ActivationManager(running_activation, container_engine=engine)

    with pytest.raises(exceptions.ActivationStartError) as exc:
        manager.start()

    assert isinstance(
        exc.value.__cause__, engine_exceptions.ContainerCleanupError
    )
    running_activation.refresh_from_db()
    process.refresh_from_db()
    assert running_activation.status == enums.ActivationStatus.ERROR
    assert process.status == enums.ActivationStatus.RUNNING
    assert process.activation_pod_id == "test-pod-id"
    assert (
        models.RulebookProcess.objects.filter(
            activation=running_activation
        ).count()
        == 1
    )
    assert engine.namespace == "new-ns"
    engine.start.assert_not_called()

    engine.cleanup.side_effect = None
    engine.start.return_value = "replacement-pod-id"
    manager.start()

    process.refresh_from_db()
    assert process.status == enums.ActivationStatus.STOPPED
    assert running_activation.latest_instance.id != process.id
    engine.start.assert_called_once()


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


@pytest.mark.django_db
def test_stop_already_stopped(
    activation_with_instance: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
):
    """Test stop verb when activation is stopped."""
    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=activation_with_instance,
    )

    activation_with_instance.status = enums.ActivationStatus.STOPPED
    activation_with_instance.latest_instance.status = (
        enums.ActivationStatus.STOPPED
    )
    activation_with_instance.latest_instance.save(
        update_fields=["status"],
    )
    activation_with_instance.save(update_fields=["status"])

    activation_manager.stop()
    assert "Stopping" in eda_caplog.text
    assert "already stopped" in eda_caplog.text
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
    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=running_activation,
    )

    activation_manager.stop()
    assert "Stopping" in eda_caplog.text
    assert "Cleanup operation requested" in eda_caplog.text
    assert "Activation stopped." in eda_caplog.text
    assert running_activation.status == after_status
    assert (
        running_activation.latest_instance.status
        == enums.ActivationStatus.STOPPED
    )
    assert running_activation.latest_instance.activation_pod_id is None
    assert running_activation.status_message == after_msg
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


@pytest.mark.parametrize(
    ("initial_status", "expected_status", "expected_message"),
    [
        (
            enums.ActivationStatus.COMPLETED,
            enums.ActivationStatus.COMPLETED,
            "is already stopped.",
        ),
        (
            enums.ActivationStatus.ERROR,
            enums.ActivationStatus.ERROR,
            "is already stopped.",
        ),
        (
            enums.ActivationStatus.FAILED,
            enums.ActivationStatus.FAILED,
            "is already stopped.",
        ),
        (
            enums.ActivationStatus.STOPPED,
            enums.ActivationStatus.STOPPED,
            "is already stopped.",
        ),
        (
            enums.ActivationStatus.STOPPING,
            enums.ActivationStatus.STOPPED,
            "Activation stopped.",
        ),
        (
            enums.ActivationStatus.PENDING,
            enums.ActivationStatus.STOPPED,
            "Activation stopped.",
        ),
        (
            enums.ActivationStatus.UNRESPONSIVE,
            enums.ActivationStatus.STOPPED,
            "Activation stopped.",
        ),
    ],
)
@pytest.mark.django_db
def test_stop_with_different_statuses(
    activation_with_instance: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
    initial_status: enums.ActivationStatus,
    expected_status: enums.ActivationStatus,
    expected_message: str,
):
    """Test stop with different initial statuses."""
    # Setup initial state
    activation_with_instance.status = initial_status
    activation_with_instance.save(update_fields=["status"])
    activation_with_instance.latest_instance.status = initial_status
    activation_with_instance.latest_instance.save(update_fields=["status"])

    activation_manager = ActivationManager(
        activation_with_instance, container_engine_mock
    )

    # Execute
    activation_manager.stop()

    # Assert final state
    activation_with_instance.refresh_from_db()
    assert activation_with_instance.status == expected_status
    assert expected_message in eda_caplog.text


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


CANCEL_RESTART_PATH = (
    "aap_eda.services.activation.activation_manager"
    ".system_cancel_restart_activation"
)


@pytest.mark.django_db
def test_stop_cancels_pending_auto_restart(
    running_activation: models.Activation,
    container_engine_mock: MagicMock,
):
    """Test that stop() cancels any pending auto-restart timer."""
    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=running_activation,
    )

    with patch(CANCEL_RESTART_PATH) as mock_cancel:
        activation_manager.stop()

    mock_cancel.assert_called_once_with(
        enums.ProcessParentType.ACTIVATION,
        running_activation.id,
    )


@pytest.mark.django_db
def test_stop_cancels_auto_restart_when_already_stopped(
    activation_with_instance: models.Activation,
    container_engine_mock: MagicMock,
):
    """Test that stop() cancels auto-restart even when already stopped.

    This is critical: a pending auto-restart timer from a previous failure
    must be cancelled even if the activation is already in a stopped state.
    """
    activation_with_instance.status = enums.ActivationStatus.STOPPED
    activation_with_instance.latest_instance.status = (
        enums.ActivationStatus.STOPPED
    )
    activation_with_instance.latest_instance.save(update_fields=["status"])
    activation_with_instance.save(update_fields=["status"])

    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=activation_with_instance,
    )

    with patch(CANCEL_RESTART_PATH) as mock_cancel:
        activation_manager.stop()

    mock_cancel.assert_called_once_with(
        enums.ProcessParentType.ACTIVATION,
        activation_with_instance.id,
    )


@pytest.mark.django_db
def test_stop_cancels_auto_restart_when_no_instance(
    basic_activation: models.Activation,
    container_engine_mock: MagicMock,
):
    """Test that stop() cancels auto-restart even with no instance."""
    activation_manager = ActivationManager(
        container_engine=container_engine_mock,
        db_instance=basic_activation,
    )

    with patch(CANCEL_RESTART_PATH) as mock_cancel:
        activation_manager.stop()

    mock_cancel.assert_called_once_with(
        enums.ProcessParentType.ACTIVATION,
        basic_activation.id,
    )


SYSTEM_RESTART_PATH = (
    "aap_eda.services.activation.activation_manager"
    ".system_restart_activation"
)


@pytest.mark.django_db
def test_unresponsive_policy_skips_restart_on_cleanup_failure(
    starting_activation: models.Activation,
    container_engine_mock: MagicMock,
    failing_cleanup,
):
    """When cleanup fails, _unresponsive_policy should not restart."""
    activation = starting_activation
    activation.restart_policy = enums.RestartPolicy.ON_FAILURE
    activation.save(update_fields=["restart_policy"])

    activation_manager = ActivationManager(
        db_instance=activation,
        container_engine=container_engine_mock,
    )

    with patch(SYSTEM_RESTART_PATH) as restart_mock:
        activation_manager._unresponsive_policy(check_type="Readiness")

    restart_mock.assert_not_called()
    activation.refresh_from_db()
    assert activation.status == enums.ActivationStatus.FAILED


@pytest.mark.django_db
def test_unresponsive_policy_restarts_on_cleanup_success(
    starting_activation: models.Activation,
    container_engine_mock: MagicMock,
):
    """When cleanup succeeds and restart policy allows, restart is called."""
    activation = starting_activation
    activation.restart_policy = enums.RestartPolicy.ON_FAILURE
    activation.save(update_fields=["restart_policy"])

    activation_manager = ActivationManager(
        db_instance=activation,
        container_engine=container_engine_mock,
    )

    with patch(SYSTEM_RESTART_PATH) as restart_mock:
        activation_manager._unresponsive_policy(check_type="Readiness")

    restart_mock.assert_called_once()
    activation.refresh_from_db()
    assert activation.status == enums.ActivationStatus.FAILED


@pytest.mark.django_db
def test_unresponsive_policy_never_restart_skips_restart(
    starting_activation: models.Activation,
    container_engine_mock: MagicMock,
):
    """When restart policy is NEVER, restart is not called even on success."""
    activation = starting_activation
    activation.restart_policy = enums.RestartPolicy.NEVER
    activation.save(update_fields=["restart_policy"])

    activation_manager = ActivationManager(
        db_instance=activation,
        container_engine=container_engine_mock,
    )

    with patch(SYSTEM_RESTART_PATH) as restart_mock:
        activation_manager._unresponsive_policy(check_type="Readiness")

    restart_mock.assert_not_called()
    activation.refresh_from_db()
    assert activation.status == enums.ActivationStatus.FAILED


@pytest.mark.django_db
def test_handle_unresponsive_activation_reraises_cleanup_error(
    starting_activation: models.Activation,
    container_engine_mock: MagicMock,
    failing_cleanup,
):
    """_handle_unresponsive_activation re-raises ContainerCleanupError."""
    activation = starting_activation
    activation_manager = ActivationManager(
        db_instance=activation,
        container_engine=container_engine_mock,
    )

    with pytest.raises(engine_exceptions.ContainerCleanupError):
        activation_manager._handle_unresponsive_activation(
            check_type="Readiness",
        )

    activation.refresh_from_db()
    assert activation.status == enums.ActivationStatus.FAILED


@pytest.mark.django_db
def test_handle_unresponsive_kubernetes_cleanup_failure_preserves_job(
    starting_activation: models.Activation,
):
    """Failed Job cleanup keeps the process available for a later retry."""
    activation = starting_activation
    process = activation.latest_instance
    process.activation_job_namespace = "old-ns"
    process.save(update_fields=["activation_job_namespace"])
    engine = MagicMock(spec=KubernetesEngine)
    engine.namespace = "new-ns"
    engine.cleanup.side_effect = engine_exceptions.ContainerCleanupError(
        "cleanup failed"
    )
    manager = ActivationManager(activation, container_engine=engine)

    with pytest.raises(engine_exceptions.ContainerCleanupError):
        manager._handle_unresponsive_activation(check_type="Readiness")

    activation.refresh_from_db()
    process.refresh_from_db()
    assert activation.status == enums.ActivationStatus.STARTING
    assert process.status == enums.ActivationStatus.STARTING
    assert process.activation_pod_id == "test-pod-id"
    assert process.activation_job_namespace == "old-ns"
    assert engine.namespace == "new-ns"
    engine.cleanup.assert_called_once()
    assert engine.cleanup.call_args.args[0] == "test-pod-id"


@pytest.mark.django_db
def test_handle_unresponsive_activation_fails_instance_on_success(
    starting_activation: models.Activation,
    container_engine_mock: MagicMock,
):
    """_handle_unresponsive_activation marks instance failed after cleanup."""
    activation = starting_activation
    activation_manager = ActivationManager(
        db_instance=activation,
        container_engine=container_engine_mock,
    )

    activation_manager._handle_unresponsive_activation(
        check_type="Liveness",
    )

    activation.refresh_from_db()
    assert activation.status == enums.ActivationStatus.FAILED
    assert "Liveness" in activation.status_message


# --- Namespace-aware lifecycle tests ---


@pytest.mark.django_db
def test_create_activation_instance_records_k8s_namespace(
    basic_activation: models.Activation,
    settings: SettingsWrapper,
):
    """When engine is KubernetesEngine, namespace is recorded on process."""
    override_settings = {
        "WEBSOCKET_BASE_URL": "ws://localhost:8000",
        "WEBSOCKET_SSL_VERIFY": "no",
        "RULEBOOK_LIVENESS_CHECK_SECONDS": 73,
    }
    apply_settings(settings, **override_settings)

    k8s_engine = MagicMock(spec=KubernetesEngine)
    k8s_engine.namespace = "eda-activations"

    manager = ActivationManager(
        basic_activation,
        container_engine=k8s_engine,
    )
    manager._create_activation_instance()

    process = basic_activation.latest_instance
    assert process is not None
    assert process.activation_job_namespace == "eda-activations"


@pytest.mark.django_db
@patch(
    "aap_eda.services.activation.activation_manager."
    "get_service_account_namespace",
    return_value="eda-control-plane",
)
def test_start_replaces_legacy_job_in_control_plane_namespace(
    get_control_plane_namespace,
    running_activation: models.Activation,
    preseed_credential_types,
):
    """Clean up a legacy Job before creating a target-namespace replacement."""
    legacy_process = running_activation.latest_instance
    assert legacy_process.activation_job_namespace is None

    engine = MagicMock(spec=KubernetesEngine)
    engine.namespace = "eda-activation-jobs"
    cleanup_namespaces = []
    engine.cleanup.side_effect = lambda *_: cleanup_namespaces.append(
        engine.namespace
    )
    engine.start.return_value = "replacement-job"
    manager = ActivationManager(running_activation, container_engine=engine)

    manager.start()

    legacy_process.refresh_from_db()
    replacement_process = running_activation.latest_instance
    assert cleanup_namespaces == ["eda-control-plane"]
    assert legacy_process.activation_job_namespace == "eda-control-plane"
    assert replacement_process.id != legacy_process.id
    assert replacement_process.activation_job_namespace == (
        "eda-activation-jobs"
    )
    assert engine.namespace == "eda-activation-jobs"
    get_control_plane_namespace.assert_called_once_with()


@pytest.mark.parametrize(
    ("has_previous_instance", "previous_namespace"),
    [(False, None), (True, None), (True, "aap-eda")],
)
@pytest.mark.django_db
def test_start_logs_k8s_namespace_with_activation_and_instance(
    basic_activation: models.Activation,
    preseed_credential_types,
    has_previous_instance: bool,
    previous_namespace: str | None,
):
    """Record the new Job's namespace and any known previous namespace."""
    k8s_engine = MagicMock(spec=KubernetesEngine)
    k8s_engine.namespace = "eda-activations"
    k8s_engine.start.return_value = "activation-job"
    previous_instance = None
    if has_previous_instance:
        previous_instance = models.RulebookProcess.objects.create(
            name=basic_activation.name,
            activation=basic_activation,
            organization=basic_activation.organization,
            status=enums.ActivationStatus.STOPPED,
            activation_job_namespace=previous_namespace,
        )

    manager = ActivationManager(basic_activation, container_engine=k8s_engine)
    manager.start()

    process = basic_activation.latest_instance
    assert process.activation_job_namespace == "eda-activations"
    logs = models.RulebookProcessLog.objects.filter(
        activation_instance=process,
        log__contains="Job started in namespace",
    )
    expected_log = (
        f"Activation {basic_activation.id} "
        f"(name={basic_activation.name!r}), "
        f"instance {process.id}: Job started in namespace 'eda-activations'"
    )
    if previous_namespace:
        expected_log += (
            f"; previous instance {previous_instance.id} recorded "
            "Job namespace 'aap-eda'"
        )
    assert [log.log for log in logs] == [f"{expected_log}."]


@pytest.mark.django_db
def test_failed_k8s_start_does_not_log_job_started(
    basic_activation: models.Activation,
    preseed_credential_types,
):
    k8s_engine = MagicMock(spec=KubernetesEngine)
    k8s_engine.namespace = "eda-activations"
    k8s_engine.start.side_effect = engine_exceptions.ContainerStartError(
        "job creation failed"
    )

    manager = ActivationManager(basic_activation, container_engine=k8s_engine)
    with pytest.raises(exceptions.ActivationStartError):
        manager.start()

    assert not models.RulebookProcessLog.objects.filter(
        activation_instance=basic_activation.latest_instance,
        log__contains="Job started in namespace",
    ).exists()


@pytest.mark.django_db
def test_create_activation_instance_null_namespace_non_k8s(
    basic_activation: models.Activation,
    container_engine_mock: MagicMock,
    settings: SettingsWrapper,
):
    """Non-K8s engine leaves activation_job_namespace as None."""
    override_settings = {
        "WEBSOCKET_BASE_URL": "ws://localhost:8000",
        "WEBSOCKET_SSL_VERIFY": "no",
        "RULEBOOK_LIVENESS_CHECK_SECONDS": 73,
    }
    apply_settings(settings, **override_settings)

    manager = ActivationManager(
        basic_activation,
        container_engine=container_engine_mock,
    )
    manager._create_activation_instance()

    process = basic_activation.latest_instance
    assert process is not None
    assert process.activation_job_namespace is None


@pytest.mark.django_db
def test_cleanup_uses_instance_engine_namespace(
    running_activation: models.Activation,
):
    """Cleanup targets the process's recorded namespace, not engine default."""
    k8s_engine = MagicMock(spec=KubernetesEngine)
    k8s_engine.namespace = "new-ns"

    proc = running_activation.latest_instance
    proc.activation_job_namespace = "old-ns"
    proc.save(update_fields=["activation_job_namespace"])

    namespace_during_cleanup = []

    def capture_namespace(*args, **kwargs):
        namespace_during_cleanup.append(k8s_engine.namespace)

    k8s_engine.cleanup.side_effect = capture_namespace

    manager = ActivationManager(
        running_activation,
        container_engine=k8s_engine,
    )
    manager._cleanup()

    assert k8s_engine.namespace == "new-ns"
    k8s_engine.cleanup.assert_called_once()
    assert namespace_during_cleanup == ["old-ns"]


@pytest.mark.django_db
@patch(
    "aap_eda.services.activation.activation_manager."
    "get_service_account_namespace",
    return_value="control-plane-ns",
)
def test_cleanup_records_control_plane_namespace_for_legacy_process(
    get_control_plane_namespace,
    running_activation: models.Activation,
):
    """Legacy cleanup uses and records the control-plane namespace."""
    k8s_engine = MagicMock(spec=KubernetesEngine)
    k8s_engine.namespace = "target-ns"

    proc = running_activation.latest_instance
    proc.activation_job_namespace = None
    proc.save(update_fields=["activation_job_namespace"])
    namespaces = []
    k8s_engine.cleanup.side_effect = lambda *_: namespaces.append(
        k8s_engine.namespace
    )

    manager = ActivationManager(
        running_activation,
        container_engine=k8s_engine,
    )
    manager._cleanup()

    proc.refresh_from_db()
    assert k8s_engine.namespace == "target-ns"
    assert namespaces == ["control-plane-ns"]
    assert proc.activation_job_namespace == "control-plane-ns"
    get_control_plane_namespace.assert_called_once_with()
    k8s_engine.cleanup.assert_called_once()
