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
from aap_eda.core.exceptions import StatusRequiredError, UnknownStatusError, UpdateFieldsRequiredError


@pytest.fixture()
def init_data():
    user = models.User.objects.create(
        username="tester",
        password="secret",
        first_name="Adam",
        last_name="Tester",
        email="adam@example.com",
    )
    activation = models.Activation.objects.create(
        name="activation",
        user=user,
    )
    return models.ActivationInstance.objects.create(
        name="test-instance",
        activation=activation,
    )


@pytest.mark.django_db
def test_activation_instance_save_with_errors(init_data):
    instance = init_data
    with pytest.raises(UpdateFieldsRequiredError):
        instance.save()

    with pytest.raises(UpdateFieldsRequiredError):
        instance.save(force_insert=True)

    with pytest.raises(StatusRequiredError):
        instance.save(update_fields=["status_message"])


@pytest.mark.django_db
def test_activation_instance_save_with_invalid_status(init_data):
    instance = init_data
    instance.status = "invalid"
    with pytest.raises(UnknownStatusError):
        instance.save(update_fields=["status"])


@pytest.mark.django_db
def test_activation_instance_save(init_data):
    instance = init_data

    assert instance.status == ActivationStatus.PENDING
    assert instance.status_message == ACTIVATION_STATUS_MESSAGE_MAP[instance.status]

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
        instance.status = status
        instance.save(update_fields=["status"])

        instance.refresh_from_db()
        assert instance.status_message == ACTIVATION_STATUS_MESSAGE_MAP[instance.status]
