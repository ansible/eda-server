#  Copyright 2024 Red Hat, Inc.
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

from aap_eda.core.enums import ProcessParentType
from aap_eda.core.models import Activation, EventStream
from aap_eda.tasks.orchestrator import (
    UnknownProcessParentType,
    get_process_parent,
)


def test_get_process_parent_activation():
    activation_id = 1
    activation_mock = mock.Mock(spec=Activation)
    Activation.objects.get = mock.Mock(return_value=activation_mock)

    result = get_process_parent(ProcessParentType.ACTIVATION, activation_id)

    Activation.objects.get.assert_called_once_with(id=activation_id)
    assert result == activation_mock


def test_get_process_parent_event_stream():
    event_stream_id = 1
    event_stream_mock = mock.Mock(spec=EventStream)
    EventStream.objects.get = mock.Mock(return_value=event_stream_mock)

    result = get_process_parent(
        ProcessParentType.EVENT_STREAM,
        event_stream_id,
    )

    EventStream.objects.get.assert_called_once_with(id=event_stream_id)
    assert result == event_stream_mock


def test_get_process_parent_unknown_type():
    process_parent_type = "unknown"
    parent_id = 1

    with pytest.raises(UnknownProcessParentType) as exc_info:
        get_process_parent(process_parent_type, parent_id)

    assert (
        str(exc_info.value)
        == f"Unknown process parent type {process_parent_type}"
    )
