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

import datetime
import json
import uuid
from typing import List
from unittest import mock

import pytest
import requests
from django.core.serializers.json import DjangoJSONEncoder

from aap_eda.analytics.utils import (
    collect_controllers_info,
    datetime_hook,
    extract_job_details,
)
from aap_eda.core import models


def test_datetime_hook():
    data = {
        "started_at": "2024-09-13 14:42:49.188",
        "ended_at": "2024-09-13 14:43:10,654",
    }
    data_json = json.dumps(data, cls=DjangoJSONEncoder)

    result = json.loads(data_json, object_hook=datetime_hook)

    assert isinstance(result["started_at"], datetime.datetime) is True
    assert isinstance(result["ended_at"], datetime.datetime) is True


def test_bad_datetime_hook():
    data = {
        "started_at": "2024-09-13 14:42:49.188",
        "ended_at": "bad_2024-09-13 14:43:10,654",
    }
    data_json = json.dumps(data, cls=DjangoJSONEncoder)

    result = json.loads(data_json, object_hook=datetime_hook)

    assert isinstance(result["started_at"], datetime.datetime) is True
    assert isinstance(result["ended_at"], datetime.datetime) is False


def test_extract_job_details():
    install_uuid = uuid.uuid4()
    job_id = 8018

    controllers_info = {
        "https://controller_1/": {"install_uuid": install_uuid}
    }

    job_type, job_id, retrieved_uuid = extract_job_details(
        f"https://controller_1/#/jobs/workflow/{job_id}/details/",
        controllers_info,
    )

    assert job_type == "run_workflow_template"
    assert job_id == "8018"
    assert retrieved_uuid == install_uuid

    job_type, job_id, retrieved_uuid = extract_job_details(
        f"https://controller_1/#/jobs/playbook/{job_id}/details/",
        controllers_info,
    )
    assert job_type == "run_job_template"
    assert job_id == "8018"
    assert retrieved_uuid == install_uuid

    job_type, job_id, retrieved_uuid = extract_job_details(
        f"https://invalid_controller/#/jobs/workflow/{job_id}/details/",
        controllers_info,
    )
    assert job_type is None
    assert job_id is None
    assert retrieved_uuid is None

    job_type, job_id, retrieved_uuid = extract_job_details(
        "",
        controllers_info,
    )
    assert job_type is None
    assert job_id is None
    assert retrieved_uuid is None


@pytest.mark.django_db
def test_collect_controller_info(
    aap_credentials: List[models.EdaCredential],
    default_scm_credential: models.EdaCredential,
):
    install_uuid_1 = str(uuid.uuid4())
    install_uuid_2 = str(uuid.uuid4())
    mock_resp = mock.Mock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = [
        {"install_uuid": install_uuid_1},
        {"install_uuid": install_uuid_2},
    ]

    # hosts defined in aap_credentials
    default_host = "https://first_eda_controller_url"
    new_host = "https://second_eda_controller_url"

    with mock.patch("aap_eda.analytics.utils.logger") as mock_logger:
        with mock.patch("aap_eda.analytics.utils.requests.get") as mock_get:
            mock_get.return_value = mock_resp
            data = collect_controllers_info()

            assert len(data.keys()) == 2
            assert default_host in data
            assert data[default_host]["install_uuid"] == install_uuid_1
            assert new_host in data
            assert data[new_host]["install_uuid"] == install_uuid_2

            assert mock_logger.info.call_count == 2
            mock_logger.info.assert_has_calls(
                [
                    mock.call("Use Bearer token to ping the controller."),
                    mock.call(
                        "Use Basic authentication to ping the controller."
                    ),
                ]
            )


@pytest.mark.django_db
def test_collect_controller_info_with_exception(
    default_aap_credential: models.EdaCredential,
):
    with mock.patch("aap_eda.analytics.utils.logger") as mock_logger:
        with mock.patch("aap_eda.analytics.utils.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.RequestException(
                "Bad exception"
            )
            collect_controllers_info()

            mock_logger.warning.assert_called_once_with(
                "Failed to connect with controller using credential "
                "default-aap-credential: Bad exception"
            )
