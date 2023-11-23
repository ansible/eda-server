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
from pytest_django.fixtures import SettingsWrapper

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.services.activation.engine.common import ContainerEngine
from aap_eda.services.activation.manager import (
    ACTIVATION_PATH,
    LOGGER,
    ActivationManager,
    AnsibleRulebookCmdLine,
    exceptions,
)


def apply_settings(settings: SettingsWrapper, **kwargs):
    """Apply settings."""
    for key, value in kwargs.items():
        setattr(settings, key, value)


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


@pytest.fixture
def eda_caplog(caplog_factory) -> LogCaptureFixture:
    """Fixture to capture logs from the EDA logger."""
    return caplog_factory(LOGGER)


@pytest.fixture
def default_user() -> models.User:
    """Return a default user."""
    user = models.User.objects.create(
        username="test.user",
        password="test.user.123",
        email="test.user@localhost",
    )

    models.AwxToken.objects.create(
        name="test-token", user=user, token="supersecret"
    )

    return user


@pytest.fixture
def decision_environment() -> models.DecisionEnvironment:
    """Return a default decision environment."""
    return models.DecisionEnvironment.objects.create(
        name="test-decision-environment",
        image_url="localhost:14000/test-image-url",
    )


@pytest.fixture
def activation_with_instance(
    basic_activation: models.Activation,
) -> models.Activation:
    """Return an activation with an instance."""
    models.ActivationInstance.objects.create(activation=basic_activation)
    return basic_activation


@pytest.fixture
def running_activation(activation_with_instance: models.Activation):
    """Return a running activation."""
    activation = activation_with_instance
    activation.status = ActivationStatus.RUNNING
    activation.save(update_fields=["status"])
    activation.latest_instance.status = ActivationStatus.RUNNING
    activation.latest_instance.activation_pod_id = "test-pod-id"
    activation.latest_instance.save(
        update_fields=["status", "activation_pod_id"],
    )
    return activation


@pytest.fixture
def basic_activation(
    default_user: models.User,
    decision_environment: models.DecisionEnvironment,
    default_rulebook: models.Rulebook,
) -> models.Activation:
    """Return the minimal activation."""
    return models.Activation.objects.create(
        name="test-activation",
        user=default_user,
        decision_environment=decision_environment,
        rulebook=default_rulebook,
        # rulebook_rulesets is populated by the serializer
        rulebook_rulesets=default_rulebook.rulesets,
    )


@pytest.fixture
def container_engine_mock() -> MagicMock:
    return create_autospec(ContainerEngine, instance=True)


@pytest.mark.django_db
def test_build_cmdline(
    activation_with_instance: models.Activation,
    settings: SettingsWrapper,
):
    """Test build_cmdline."""
    override_settings = {
        "WEBSOCKET_BASE_URL": "ws://localhost:8000",
        "ANSIBLE_RULEBOOK_LOG_LEVEL": "-vv",
        "WEBSOCKET_SSL_VERIFY": "no",
        "RULEBOOK_LIVENESS_CHECK_SECONDS": 73,
    }
    apply_settings(settings, **override_settings)
    activation_manager = ActivationManager(activation_with_instance)
    cmdline = activation_manager._build_cmdline()
    assert isinstance(cmdline, AnsibleRulebookCmdLine)
    assert (
        cmdline.ws_url
        == override_settings["WEBSOCKET_BASE_URL"] + ACTIVATION_PATH
    )
    assert cmdline.log_level == override_settings["ANSIBLE_RULEBOOK_LOG_LEVEL"]
    assert cmdline.ws_ssl_verify == override_settings["WEBSOCKET_SSL_VERIFY"]
    assert (
        cmdline.heartbeat
        == override_settings["RULEBOOK_LIVENESS_CHECK_SECONDS"]
    )
    assert cmdline.id == str(activation_with_instance.latest_instance.id)


@pytest.mark.django_db
def test_build_cmdline_no_instance(basic_activation):
    """Test build_cmdline when no instance exists."""
    activation_manager = ActivationManager(basic_activation)
    with pytest.raises(exceptions.ActivationManagerError):
        activation_manager._build_cmdline()


@pytest.mark.django_db
def test_build_credential_inexistent(basic_activation):
    """Test build_credential when no credential exists."""
    activation_manager = ActivationManager(basic_activation)
    assert activation_manager._build_credential() is None


@pytest.mark.django_db
def test_start_deleted_activation(activation_with_instance):
    """Test start verb when activation is deleted."""
    activation_manager = ActivationManager(activation_with_instance)
    activation_with_instance.delete()
    with pytest.raises(exceptions.ActivationStartError) as exc:
        activation_manager.start()
    assert "does not exist" in str(exc.value)


@pytest.mark.django_db
def test_start_disabled_activation(activation_with_instance, eda_caplog):
    """Test start verb when activation is deleted."""
    err_msg = "is disabled. Can not be started."
    activation_manager = ActivationManager(activation_with_instance)
    activation_with_instance.is_enabled = False
    activation_with_instance.save(update_fields=["is_enabled"])
    with pytest.raises(exceptions.ActivationStartError) as exc:
        activation_manager.start()
    assert err_msg in eda_caplog.text
    assert err_msg in str(exc.value)


@pytest.mark.django_db
def test_start_no_awx_token(basic_activation):
    """Test start verb when no AWX token is present."""
    activation_manager = ActivationManager(basic_activation)
    basic_activation.user.awxtoken_set.all().delete()
    with pytest.raises(exceptions.ActivationStartError) as exc:
        activation_manager.start()
    assert basic_activation.status == ActivationStatus.ERROR
    assert "No controller token specified" in str(exc.value)
    assert str(exc.value) in basic_activation.status_message


@pytest.mark.django_db
def test_start_no_decision_environment(basic_activation):
    """Test start verb when no decision environment is present."""
    activation_manager = ActivationManager(basic_activation)
    basic_activation.decision_environment.delete()
    with pytest.raises(exceptions.ActivationStartError) as exc:
        activation_manager.start()
    assert basic_activation.status == ActivationStatus.ERROR
    assert "decision_environment" in str(exc.value)
    assert "This field may not be null" in str(exc.value)
    assert str(exc.value) in basic_activation.status_message


@pytest.mark.django_db
def test_start_already_running(
    running_activation: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
):
    """Test start verb when activation is already running."""
    activation_manager = ActivationManager(
        db_instance=running_activation,
        container_engine=container_engine_mock,
    )
    container_engine_mock.get_status.return_value = MagicMock(
        status=ActivationStatus.RUNNING,
    )

    activation_manager.start()
    assert container_engine_mock.get_status.called
    assert "already running" in eda_caplog.text
    assert running_activation.status == ActivationStatus.RUNNING


@pytest.mark.django_db
def test_start_first_run(
    basic_activation: models.Activation,
    container_engine_mock: MagicMock,
    eda_caplog: LogCaptureFixture,
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
    assert basic_activation.status == ActivationStatus.RUNNING
    assert basic_activation.latest_instance.status == ActivationStatus.RUNNING
    assert basic_activation.latest_instance.activation_pod_id == "test-pod-id"
    assert basic_activation.restart_count == 0
