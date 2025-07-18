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

import signal
from unittest import mock

import pytest
from django.core.management import call_command
from django_rq.management.commands import rqscheduler, rqworker


@pytest.mark.django_db
@mock.patch(
    "aap_eda.core.management.commands.rqworker.features.DISPATCHERD", True
)
@mock.patch(
    "aap_eda.core.management.commands.rqworker.run_dispatcherd_service",
)
def test_rqworker_command_feature_flag_enabled(dispatcherd_service_mock):
    call_command(
        "rqworker",
        worker_class="aap_eda.core.tasking.ActivationWorker",
    )
    dispatcherd_service_mock.assert_called_once()


@pytest.mark.django_db
@mock.patch(
    "aap_eda.core.management.commands.rqworker.features.DISPATCHERD", False
)
@mock.patch.object(rqworker.Command, "handle", return_value=None)
def test_rqworker_command_feature_flag_disabled(
    mock_rqworker_handle,
):
    call_command(
        "rqworker",
        worker_class="aap_eda.core.tasking.ActivationWorker",
    )

    mock_rqworker_handle.assert_called_once()


@pytest.mark.django_db
@mock.patch(
    "aap_eda.core.management.commands.scheduler.features.DISPATCHERD", False
)
@mock.patch.object(rqscheduler.Command, "handle", return_value=None)
def test_rqscheduler_command_feature_flag_disabled(
    mock_rqscheduler_handle,
):
    call_command("scheduler")

    mock_rqscheduler_handle.assert_called_once()


@pytest.mark.django_db
@mock.patch(
    "aap_eda.core.management.commands.scheduler.features.DISPATCHERD", True
)
@mock.patch("time.sleep")
def test_rqscheduler_command_feature_flag_enabled(
    mock_sleep,
    capsys,
):
    def fake_sleep(_):
        signal.raise_signal(signal.SIGTERM)

    mock_sleep.side_effect = fake_sleep
    call_command("scheduler")
    captured = capsys.readouterr()
    assert "This command is not required" in captured.out
    assert "Exiting noop mode." in captured.out
