#  Copyright 2025 Red Hat, Inc.
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
from django.conf import settings
from django.core.management import call_command
from django.test import override_settings
from django_rq.management.commands import rqscheduler, rqworker


@override_settings(
    FLAGS={
        settings.DISPATCHERD_FEATURE_FLAG_NAME: [
            {"condition": "boolean", "value": True},
        ],
    }
)
@pytest.mark.django_db
def test_rqworker_command_feature_flag_enabled(capsys):
    with pytest.raises(SystemExit) as exc_info:
        call_command(
            "rqworker",
            worker_class="aap_eda.core.tasking.ActivationWorker",
        )
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "DISPATCHERD feature not implemented yet" in captured.err


@override_settings(
    FLAGS={
        settings.DISPATCHERD_FEATURE_FLAG_NAME: [
            {"condition": "boolean", "value": False},
        ],
    }
)
@pytest.mark.django_db
@mock.patch.object(rqworker.Command, "handle", return_value=None)
def test_rqworker_command_feature_flag_disabled(
    mock_rqworker_handle,
):
    call_command(
        "rqworker",
        worker_class="aap_eda.core.tasking.ActivationWorker",
    )

    mock_rqworker_handle.assert_called_once()


@override_settings(
    FLAGS={
        settings.DISPATCHERD_FEATURE_FLAG_NAME: [
            {"condition": "boolean", "value": False},
        ],
    }
)
@pytest.mark.django_db
@mock.patch.object(rqscheduler.Command, "handle", return_value=None)
def test_rqscheduler_command_feature_flag_disabled(
    mock_rqscheduler_handle,
):
    call_command("scheduler")

    mock_rqscheduler_handle.assert_called_once()


@override_settings(
    FLAGS={
        settings.DISPATCHERD_FEATURE_FLAG_NAME: [
            {"condition": "boolean", "value": True},
        ],
    }
)
@pytest.mark.django_db
@mock.patch.object(rqscheduler.Command, "handle", return_value=None)
def test_rqscheduler_command_feature_flag_enabled(
    mock_rqscheduler_handle,
    capsys,
):
    with pytest.raises(SystemExit) as exc_info:
        call_command("scheduler")
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "This command is not supported" in captured.err
