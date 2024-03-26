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
from pytest_lazyfixture import lazy_fixture

from aap_eda.core import enums, models
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
    activation = models.Activation.objects.create(
        name="activation",
        user=user,
    )
    return models.RulebookProcess.objects.create(
        name="test-instance",
        activation=activation,
    )


@pytest.mark.django_db
def test_rulebook_process_save_with_errors(init_data):
    instance = init_data
    with pytest.raises(UpdateFieldsRequiredError):
        instance.save()

    with pytest.raises(UpdateFieldsRequiredError):
        instance.save(force_insert=True)

    with pytest.raises(StatusRequiredError):
        instance.save(update_fields=["status_message"])


@pytest.mark.django_db
def test_rulebook_process_save_with_invalid_status(init_data):
    instance = init_data
    instance.status = "invalid"
    with pytest.raises(UnknownStatusError):
        instance.save(update_fields=["status"])


@pytest.mark.django_db
def test_rulebook_process_save(init_data):
    instance = init_data

    assert instance.status == enums.ActivationStatus.PENDING
    assert (
        instance.status_message
        == enums.ACTIVATION_STATUS_MESSAGE_MAP[instance.status]
    )

    for status in [
        enums.ActivationStatus.STARTING,
        enums.ActivationStatus.RUNNING,
        enums.ActivationStatus.STOPPING,
        enums.ActivationStatus.DELETING,
        enums.ActivationStatus.COMPLETED,
        enums.ActivationStatus.FAILED,
        enums.ActivationStatus.STOPPED,
        enums.ActivationStatus.UNRESPONSIVE,
        enums.ActivationStatus.ERROR,
        enums.ActivationStatus.PENDING,
    ]:
        instance.status = status
        instance.save(update_fields=["status"])

        instance.refresh_from_db()
        assert (
            instance.status_message
            == enums.ACTIVATION_STATUS_MESSAGE_MAP[instance.status]
        )


@pytest.mark.parametrize(
    "instance",
    [
        pytest.param(
            lazy_fixture("new_rulebook_process_with_activation"),
            id="activation",
        ),
        pytest.param(
            lazy_fixture("new_rulebook_process_with_event_stream"),
            id="event_stream",
        ),
    ],
)
@pytest.mark.django_db
def test_rulebook_process_parent_type(instance):
    """Test parent_type field is updated when a new instance is created."""
    if instance.activation:
        assert instance.parent_type == enums.ProcessParentType.ACTIVATION
    else:
        assert instance.parent_type == enums.ProcessParentType.EVENT_STREAM


@pytest.mark.parametrize(
    "instance",
    [
        pytest.param(
            lazy_fixture("new_rulebook_process_with_activation"),
            id="activation",
        ),
        pytest.param(
            lazy_fixture("new_rulebook_process_with_event_stream"),
            id="event_stream",
        ),
    ],
)
@pytest.mark.django_db
def test_rulebook_process_get_parent(instance):
    """Test get_parent method returns the correct parent instance."""
    if instance.activation:
        assert instance.get_parent() == instance.activation
    else:
        assert instance.get_parent() == instance.event_stream
