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
from aap_eda.core.enums import (
    ACTIVATION_STATUS_MESSAGE_MAP,
    ActivationStatus,
    RestartPolicy,
)
from aap_eda.services.ruleset.activate_rulesets import ActivateRulesets
from aap_eda.tasks.ruleset import (
    _activate,
    _monitor_activations,
    deactivate,
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
        status=ActivationStatus.COMPLETED,
        updated_at=now
        - timedelta(seconds=settings.RULEBOOK_LIVENESS_TIMEOUT_SECONDS + 1),
    )
    instance2 = models.ActivationInstance.objects.create(
        activation=activation,
        status=ActivationStatus.RUNNING,
        updated_at=now
        - timedelta(seconds=settings.RULEBOOK_LIVENESS_TIMEOUT_SECONDS + 1),
    )

    return InitData(
        user=user,
        activation=activation,
        instance1=instance1,
        instance2=instance2,
    )


@pytest.fixture()
def init_activation():
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
        is_enabled=True,
        is_valid=True,
        failure_count=1,
        status=ActivationStatus.FAILED,
        status_updated_at=timezone.now()
        - timedelta(
            seconds=settings.ACTIVATION_RESTART_SECONDS_ON_FAILURE + 1
        ),
    )

    return activation


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
        _activate(activation.id, activation.user.username)

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
        _activate(activation.id)

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
        _activate(activation.id)

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
@mock.patch("aap_eda.tasks.ruleset.validate_activation", return_value=True)
@mock.patch("aap_eda.tasks.ruleset.logger.info")
@mock.patch("aap_eda.tasks.ruleset.activate")
def test_restart(
    delay_mock: mock.Mock,
    info_mock: mock.Mock,
    validate_mock: mock.Mock,
    init_data,
):
    job = mock.Mock()
    job.id = "jid"
    delay_mock.return_value = job
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
    activation.refresh_from_db()
    assert activation.current_job_id == "jid"


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.deactivate")
def test_monitor_activations_to_unresponsive(
    deactivate_mock: mock.Mock, init_data
):
    _monitor_activations()
    init_data.instance1.refresh_from_db()
    init_data.instance2.refresh_from_db()

    assert init_data.instance2.status == ActivationStatus.UNRESPONSIVE
    assert init_data.instance1.status == ActivationStatus.COMPLETED
    deactivate_mock.assert_called_once_with(
        activation_id=init_data.activation.id,
        requester="SCHEDULER",
        delete=False,
    )


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.validate_activation", return_value=True)
@mock.patch("aap_eda.tasks.ruleset.activate")
def test_monitor_activations_restart_completed(
    activate_mock: mock.Mock, validate_mock: mock.Mock, init_activation
):
    job = mock.Mock()
    job.id = "jid"
    activate_mock.return_value = job
    init_activation.restart_policy = RestartPolicy.ALWAYS
    init_activation.status = ActivationStatus.COMPLETED
    init_activation.status_updated_at = timezone.now() - timedelta(
        seconds=settings.ACTIVATION_RESTART_SECONDS_ON_COMPLETE + 1
    )
    init_activation.save(
        update_fields=["status", "status_updated_at", "restart_policy"]
    )
    _monitor_activations()

    activate_mock.assert_called_once_with(
        activation_id=init_activation.id,
        requester="SCHEDULER",
    )
    init_activation.refresh_from_db()
    assert init_activation.current_job_id == "jid"
    assert (
        init_activation.status_message
        == ACTIVATION_STATUS_MESSAGE_MAP[init_activation.status]
    )


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.validate_activation", return_value=True)
@mock.patch("aap_eda.tasks.ruleset.activate")
def test_monitor_activations_restart_failed(
    activate_mock: mock.Mock, validate_mock: mock.Mock, init_activation
):
    job = mock.Mock()
    job.id = "jid"
    activate_mock.return_value = job
    _monitor_activations()

    activate_mock.assert_called_once_with(
        activation_id=init_activation.id, requester="SCHEDULER"
    )
    init_activation.refresh_from_db()
    assert init_activation.current_job_id == "jid"


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.validate_activation", return_value=False)
@mock.patch("aap_eda.tasks.ruleset.activate")
@mock.patch("aap_eda.tasks.ruleset.logger.info")
def test_monitor_activations_with_invalid_activation(
    info_mock: mock.Mock,
    activate_mock: mock.Mock,
    validate_mock: mock.Mock,
    init_activation,
):
    job = mock.Mock()
    job.id = "jid"
    activate_mock.return_value = job
    _monitor_activations()

    msg1 = "Task started: monitor_activations"
    msg2 = "Restart activation test according to its restart policy."
    msg3 = "Activation test failed to restart due to its invalid state"
    info_mock.assert_has_calls(
        [mock.call(msg1), mock.call(msg2), mock.call(msg3)]
    )


@pytest.mark.parametrize(
    "activation_attrs",
    [
        {
            "status_updated_at": timezone.now()
            - timedelta(
                seconds=settings.ACTIVATION_RESTART_SECONDS_ON_FAILURE - 75
            )
        },
        {
            "restart_policy": RestartPolicy.ALWAYS,
            "status": ActivationStatus.COMPLETED,
            "status_updated_at": timezone.now()
            - timedelta(
                seconds=settings.ACTIVATION_RESTART_SECONDS_ON_COMPLETE - 75
            ),
        },
        {"restart_policy": RestartPolicy.NEVER},
        {"is_valid": False},
        {"failure_count": settings.ACTIVATION_MAX_RESTARTS_ON_FAILURE + 1},
    ],
)
@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.activate")
def test_monitor_activations_not_restart(
    activate_mock: mock.Mock, init_activation, activation_attrs
):
    job = mock.Mock()
    job.id = "jid"
    activate_mock.return_value = job

    update_fields = []
    for key in activation_attrs:
        setattr(init_activation, key, activation_attrs[key])
        update_fields.append(key)
    init_activation.save(update_fields=update_fields)
    _monitor_activations()

    activate_mock.assert_not_called()
