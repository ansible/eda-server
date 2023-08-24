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
from dataclasses import dataclass
from datetime import timedelta
from unittest import mock

import pytest
from django.conf import settings
from django.utils import timezone

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.services.ruleset.activate_rulesets import ActivateRulesets
from aap_eda.tasks.ruleset import (
    activate,
    deactivate,
    monitor_activations,
    restart,
)


@dataclass
class InitData:
    user: models.User
    activation: models.Activation
    instance1: models.ActivationInstance
    instance2: models.ActivationInstance


@pytest.fixture()
def init_data():
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    activation = models.Activation.objects.create(
        name="test",
        user=user,
    )
    now = timezone.now()
    instance1 = models.ActivationInstance.objects.create(
        activation=activation,
        status=ActivationStatus.COMPLETED.value,
        updated_at=now
        - timedelta(int(settings.RULEBOOK_LIVENESS_TIMEOUT_SECONDS) + 1),
    )
    instance2 = models.ActivationInstance.objects.create(
        activation=activation,
        status=ActivationStatus.RUNNING.value,
        updated_at=now
        - timedelta(int(settings.RULEBOOK_LIVENESS_TIMEOUT_SECONDS) + 1),
    )

    return InitData(
        user=user,
        activation=activation,
        instance1=instance1,
        instance2=instance2,
    )


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.logger.info")
def test_normal_activate(info_mock: mock.Mock, init_data):
    activation = models.Activation.objects.create(
        name="test-activate",
        user=init_data.user,
    )

    msg1 = (
        f"Activating activation id: {activation.id} requested"
        f" by {activation.user.username}"
    )
    msg2 = f"Activation {activation.name} is done."

    with mock.patch.object(ActivateRulesets, "activate"):
        activate(activation.id, activation.user.username)

    info_mock.assert_has_calls([mock.call(msg1), mock.call(msg2)])


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.logger.info")
def test_not_enabled_activate(info_mock: mock.Mock, init_data):
    activation = models.Activation.objects.create(
        name="test-activate",
        user=init_data.user,
        is_enabled=False,
    )

    msg1 = f"Activating activation id: {activation.id} requested by User"
    msg2 = f"Activation id: {activation.id} is disabled"

    with mock.patch.object(ActivateRulesets, "activate"):
        activate(activation.id)

    info_mock.assert_has_calls([mock.call(msg1), mock.call(msg2)])


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.logger.info")
def test_with_deleting_activate(info_mock: mock.Mock, init_data):
    activation = models.Activation.objects.create(
        name="test-activate",
        user=init_data.user,
        status=ActivationStatus.DELETING,
    )

    msg1 = f"Activating activation id: {activation.id} requested by User"
    msg2 = f"Activation id: {activation.id} is deleted"

    with mock.patch.object(ActivateRulesets, "activate"):
        activate(activation.id)

    info_mock.assert_has_calls([mock.call(msg1), mock.call(msg2)])


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.logger.info")
def test_deactivate(info_mock: mock.Mock, init_data):
    activation = models.Activation.objects.create(
        name="test-activate",
        user=init_data.user,
    )
    msg = (
        f"Disabling activation id: {activation.id} requested"
        f" by {activation.user.username}"
    )

    with mock.patch("aap_eda.tasks.ruleset._perform_deactivate"):
        deactivate(activation.id, activation.user.username)

    info_mock.assert_called_once_with(msg)


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.logger.info")
def test_deactivate_with_delete(info_mock: mock.Mock, init_data):
    activation = models.Activation.objects.create(
        name="test-activate",
        user=init_data.user,
    )
    msg1 = (
        f"Disabling activation id: {activation.id} requested"
        f" by {activation.user.username}"
    )
    msg2 = f"Activation {activation.name} is deleted"

    with mock.patch("aap_eda.tasks.ruleset._perform_deactivate"):
        deactivate(activation.id, activation.user.username, True)

    info_mock.assert_has_calls([mock.call(msg1), mock.call(msg2)])


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.logger.info")
@mock.patch("aap_eda.tasks.ruleset.activate.delay")
def test_restart(delay_mock: mock.Mock, info_mock: mock.Mock, init_data):
    activation = models.Activation.objects.create(
        name="test-activate",
        user=init_data.user,
    )
    msg = (
        f"Restarting activation id: {activation.id} requested"
        f" by {activation.user.username}"
    )

    with mock.patch("aap_eda.tasks.ruleset._perform_deactivate"):
        restart(activation.id, activation.user.username)

    info_mock.assert_called_once_with(msg)


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.activate.delay")
def test_monitor_activations_to_unknown(delay_mock: mock.Mock, init_data):
    monitor_activations()
    init_data.instance1.refresh_from_db()
    init_data.instance2.refresh_from_db()

    assert init_data.instance2.status == ActivationStatus.UNRESPONSIVE.value
    assert init_data.instance1.status == ActivationStatus.COMPLETED.value
    delay_mock.assert_not_called()


@pytest.mark.skip(reason="do not proceed restart at this moment")
@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.activate_rulesets.delay")
def test_monitor_activations_restart(delay_mock: mock.Mock, init_data):
    init_data.instance2.status = ActivationStatus.UNRESPONSIVE.value
    init_data.instance2.save()
    monitor_activations()

    delay_mock.assert_called_once_with(
        is_restart=True,
        activation_id=init_data.activation.id,
        deployment_type=settings.DEPLOYMENT_TYPE,
        ws_base_url=settings.WEBSOCKET_BASE_URL,
        ssl_verify=settings.WEBSOCKET_SSL_VERIFY,
    )
