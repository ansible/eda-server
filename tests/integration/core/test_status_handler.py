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

from aap_eda.core.enums import ACTIVATION_STATUS_MESSAGE_MAP, ActivationStatus
from aap_eda.core.exceptions import (
    StatusRequiredError,
    UnknownStatusError,
    UpdateFieldsRequiredError,
)


@pytest.mark.parametrize(
    "instance",
    [
        pytest.param(
            lazy_fixture("new_activation"),
            id="activation",
        ),
        pytest.param(
            lazy_fixture("new_event_stream"),
            id="event_stream",
        ),
    ],
)
@pytest.mark.django_db
def test_save_with_errors(instance):
    with pytest.raises(UpdateFieldsRequiredError):
        instance.save()

    with pytest.raises(StatusRequiredError):
        instance.save(update_fields=["status_message"])


@pytest.mark.parametrize(
    "instance",
    [
        pytest.param(
            lazy_fixture("new_activation"),
            id="activation",
        ),
        pytest.param(
            lazy_fixture("new_event_stream"),
            id="event_stream",
        ),
    ],
)
@pytest.mark.django_db
def test_save_with_invalid_status(instance):
    instance.status = "invalid"
    with pytest.raises(UnknownStatusError):
        instance.save(update_fields=["status"])

    with pytest.raises(UpdateFieldsRequiredError):
        instance.save(force_insert=True)

    instance.status_message = "invalid message"
    with pytest.raises(UnknownStatusError):
        instance.save(update_fields=["status", "status_message"])


@pytest.mark.parametrize(
    "instance",
    [
        pytest.param(
            lazy_fixture("new_activation"),
            id="activation",
        ),
        pytest.param(
            lazy_fixture("new_event_stream"),
            id="event_stream",
        ),
    ],
)
@pytest.mark.django_db
def test_save(instance):
    assert instance.is_enabled is True
    assert instance.status == ActivationStatus.PENDING
    assert (
        instance.status_message
        == ACTIVATION_STATUS_MESSAGE_MAP[instance.status]
    )

    for status in ActivationStatus:
        instance.status = status.value
        instance.save(update_fields=["status"])

        instance.refresh_from_db()
        assert (
            instance.status_message
            == ACTIVATION_STATUS_MESSAGE_MAP[instance.status]
        )

    instance.is_enabled = False
    instance.save(update_fields=["is_enabled"])
    instance.refresh_from_db()
    assert instance.is_enabled is False

    instance.status = ActivationStatus.PENDING
    instance.save(update_fields=["status"])
    instance.refresh_from_db()
    assert instance.status_message == "Activation is marked as disabled"

    instance.status = ActivationStatus.ERROR
    error_message = "activation is in error state"
    instance.status_message = error_message
    instance.save(update_fields=["status", "status_message"])

    instance.refresh_from_db()
    assert instance.status == ActivationStatus.ERROR
    assert instance.status_message == error_message
