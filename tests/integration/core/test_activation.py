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


import pytest

from aap_eda.core import models
from aap_eda.core.enums import ACTIVATION_STATUS_MESSAGE_MAP, ActivationStatus
from aap_eda.core.exceptions import (
    StatusRequiredError,
    UnknownStatusError,
    UpdateFieldsRequiredError,
)


@pytest.fixture()
def init_data():
    user = models.User.objects.create(
        username="tester",
        password="secret",
        first_name="Adam",
        last_name="Tester",
        email="adam@example.com",
    )
    return models.Activation.objects.create(
        name="activation",
        user=user,
    )


@pytest.mark.django_db
def test_activation_save_with_errors(init_data):
    activation = init_data
    with pytest.raises(UpdateFieldsRequiredError):
        activation.save()

    with pytest.raises(StatusRequiredError):
        activation.save(update_fields=["status_message"])


@pytest.mark.django_db
def test_activation_save_with_invalid_status(init_data):
    activation = init_data
    activation.status = "invalid"
    with pytest.raises(UnknownStatusError):
        activation.save(update_fields=["status"])

    with pytest.raises(UpdateFieldsRequiredError):
        activation.save(force_insert=True)

    activation.status_message = "invalid message"
    with pytest.raises(UnknownStatusError):
        activation.save(update_fields=["status", "status_message"])


@pytest.mark.django_db
def test_activation_save(init_data):
    activation = init_data

    assert activation.is_enabled is True
    assert activation.status == ActivationStatus.PENDING
    assert (
        activation.status_message
        == ACTIVATION_STATUS_MESSAGE_MAP[activation.status]
    )

    for status in [
        ActivationStatus.STARTING,
        ActivationStatus.RUNNING,
        ActivationStatus.STOPPING,
        ActivationStatus.DELETING,
        ActivationStatus.COMPLETED,
        ActivationStatus.FAILED,
        ActivationStatus.STOPPED,
        ActivationStatus.UNRESPONSIVE,
        ActivationStatus.ERROR,
        ActivationStatus.PENDING,
    ]:
        activation.status = status
        activation.save(update_fields=["status"])

        activation.refresh_from_db()
        assert (
            activation.status_message
            == ACTIVATION_STATUS_MESSAGE_MAP[activation.status]
        )

    activation.is_enabled = False
    activation.save(update_fields=["is_enabled"])
    activation.refresh_from_db()
    assert activation.is_enabled is False

    activation.save(update_fields=["status"])
    activation.refresh_from_db()
    assert activation.status_message == "Activation is marked as disabled"

    activation.status = ActivationStatus.ERROR
    error_message = "activation is in error state"
    activation.status_message = error_message
    activation.save(update_fields=["status", "status_message"])

    activation.refresh_from_db()
    assert activation.status == ActivationStatus.ERROR
    assert activation.status_message == error_message
