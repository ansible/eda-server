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

import uuid
from unittest import mock

import pytest
from aap_eda.core import models
from aap_eda.core.enums import ActivationRequest
from aap_eda.services.activation.restart_helper import (
    _queue_auto_start,
    system_restart_activation,
)
from pytest_lazyfixture import lazy_fixture


@pytest.fixture()
def proxy_with_instance():
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    instance = models.Activation.objects.create(
        name="test1",
        user=user,
    )
    return models.ProcessParentProxy(instance)


@pytest.fixture()
def proxy_with_source():
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    instance = models.Source.objects.create(
        uuid=uuid.uuid4(),
        name="test-source",
        type="ansible.eda.generic",
        args='{"a": 1, "b": 2}',
        user=user,
    )
    return models.ProcessParentProxy(instance)


@pytest.mark.parametrize(
    "process_parent",
    [
        pytest.param(
            lazy_fixture("proxy_with_instance"),
            id="stopped",
        ),
        pytest.param(
            lazy_fixture("proxy_with_source"),
            id="error",
        ),
    ],
)
@pytest.mark.django_db
@mock.patch("aap_eda.services.activation.restart_helper.enqueue_delay")
def test_system_restart_activation(enqueue_mock, process_parent):
    system_restart_activation(process_parent, 5)
    enqueue_args = [
        "default",
        5,
        _queue_auto_start,
    ]
    enqueue_mock.assert_called_once_with(
        *enqueue_args,
        process_parent_data=process_parent.to_dict(),
    )


@pytest.mark.parametrize(
    "process_parent",
    [
        pytest.param(
            lazy_fixture("proxy_with_instance"),
            id="stopped",
        ),
        pytest.param(
            lazy_fixture("proxy_with_source"),
            id="error",
        ),
    ],
)
@pytest.mark.django_db
def test_queue_auto_start(process_parent):
    _queue_auto_start(process_parent.to_dict())
    queued = models.ActivationRequestQueue.objects.first()
    if process_parent.is_activation:
        assert queued.activation == process_parent.instance

    else:
        assert queued.source == process_parent.instance
    assert queued.request == ActivationRequest.AUTO_START
