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


import pytest
from pytest_django.fixtures import SettingsWrapper

from aap_eda.core import models
from aap_eda.services.activation.manager import (
    ACTIVATION_PATH,
    ActivationManager,
    AnsibleRulebookCmdLine,
    exceptions,
)


def apply_settings(settings: SettingsWrapper, **kwargs):
    """Apply settings."""
    for key, value in kwargs.items():
        setattr(settings, key, value)


# TODO(alex) dedup code and fixtures across all the tests
@pytest.fixture
def default_user() -> models.User:
    """Return a default user."""
    return models.User.objects.create(
        username="test.user",
        password="test.user.123",
        email="test.user@localhost",
    )


@pytest.fixture
def activation_with_instance(default_user: models.User) -> models.Activation:
    """Return an activation with an instance."""
    activation = models.Activation.objects.create(
        name="test-activation",
        user=default_user,
    )
    models.ActivationInstance.objects.create(activation=activation)
    return activation


@pytest.fixture
def basic_activation(default_user: models.User) -> models.Activation:
    """Return the minimal activation."""
    decision_environment = models.DecisionEnvironment.objects.create(
        name="test-decision-environment",
        image_url="localhost:14000/test-image-url",
    )

    return models.Activation.objects.create(
        name="test-activation",
        user=default_user,
        decision_environment=decision_environment,
    )


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
