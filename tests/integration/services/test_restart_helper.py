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

from unittest import mock

import pytest

from aap_eda.core import models
from aap_eda.core.enums import ActivationRequest, ProcessParentType
from aap_eda.services.activation.restart_helper import (
    _queue_auto_start,
    auto_start_job_id,
    system_restart_activation,
)


@pytest.fixture()
def activation():
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    return models.Activation.objects.create(
        name="test1",
        user=user,
    )


@pytest.mark.django_db
@mock.patch("aap_eda.services.activation.restart_helper.enqueue_delay")
def test_system_restart_activation(enqueue_mock, activation):
    system_restart_activation(ProcessParentType.ACTIVATION, activation.id, 5)
    enqueue_args = [
        "default",
        auto_start_job_id(ProcessParentType.ACTIVATION, activation.id),
        5,
        _queue_auto_start,
        ProcessParentType.ACTIVATION,
        activation.id,
    ]
    enqueue_mock.assert_called_once_with(*enqueue_args)


@pytest.mark.django_db
def test_queue_auto_start(activation):
    _queue_auto_start(ProcessParentType.ACTIVATION, activation.id)

    queued = models.ActivationRequestQueue.objects.first()
    assert queued.process_parent_type == ProcessParentType.ACTIVATION
    assert queued.process_parent_id == activation.id
    assert queued.request == ActivationRequest.AUTO_START
