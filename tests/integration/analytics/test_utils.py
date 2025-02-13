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

import json
import uuid
from datetime import datetime
from typing import List
from unittest import mock

import pytest
import yaml
from django.core.serializers.json import DjangoJSONEncoder
from requests import Request
from requests.exceptions import RequestException

from aap_eda.analytics.utils import (
    TokenAuth,
    collect_controllers_info,
    datetime_hook,
    extract_job_details,
)
from aap_eda.core import models


@pytest.fixture
def basic_request():
    return Request(
        method="GET",
        url="https://example.com",
        headers={"Content-Type": "application/json"},
    ).prepare()


def test_datetime_hook():
    data = {
        "started_at": "2024-09-13 14:42:49.188",
        "ended_at": "2024-09-13 14:43:10,654",
    }
    data_json = json.dumps(data, cls=DjangoJSONEncoder)

    result = json.loads(data_json, object_hook=datetime_hook)

    assert isinstance(result["started_at"], datetime) is True
    assert isinstance(result["ended_at"], datetime) is True


def test_datetime_hook_error_handling():
    with mock.patch(
        "aap_eda.analytics.utils.parse_datetime", side_effect=TypeError
    ):
        test_data = {
            "bad_date": "invalid-date",
            "number": 123,
            "nested": {"key": "2023-01-01T00:00:00Z"},
        }

        result = datetime_hook(test_data)

        assert result == test_data


def test_bad_datetime_hook():
    data = {
        "started_at": "2024-09-13 14:42:49.188",
        "ended_at": "bad_2024-09-13 14:43:10,654",
    }
    data_json = json.dumps(data, cls=DjangoJSONEncoder)

    result = json.loads(data_json, object_hook=datetime_hook)

    assert isinstance(result["started_at"], datetime) is True
    assert isinstance(result["ended_at"], datetime) is False


@pytest.mark.parametrize(
    "url,controllers_info,expected",
    [
        # Playbook
        (
            "https://controller1.example.com/jobs/playbook/123/",
            {"https://controller1.example.com": {"install_uuid": "uuid-1111"}},
            ("run_job_template", "123", "uuid-1111"),
        ),
        # Workflow
        (
            "https://controller2.example.com/jobs/workflow/456/",
            {"https://controller2.example.com": {"install_uuid": "uuid-2222"}},
            ("run_workflow_template", "456", "uuid-2222"),
        ),
        # with params
        (
            "https://controller3.example.com/jobs/playbook/789/?foo=bar",
            {"https://controller3.example.com": {"install_uuid": "uuid-3333"}},
            ("run_job_template", "789", "uuid-3333"),
        ),
        # multiple controllers
        (
            "https://sub.controller4.example.com/jobs/workflow/101/",
            {
                "https://controller4.example.com": {
                    "install_uuid": "uuid-4444"
                },
                "https://sub.controller4.example.com": {
                    "install_uuid": "uuid-5555"
                },
            },
            ("run_workflow_template", "101", "uuid-5555"),
        ),
        # unmatched controller
        (
            "https://unknown.controller.com/jobs/playbook/999/",
            {"https://known.controller.com": {"install_uuid": "uuid-6666"}},
            (None, None, None),
        ),
        # unmatched url
        (
            "https://controller5.example.com/invalid/path/",
            {"https://controller5.example.com": {"install_uuid": "uuid-7777"}},
            (None, None, None),
        ),
        # no install_uuid
        (
            "https://controller6.example.com/jobs/playbook/321/",
            {"https://controller6.example.com": {}},
            (None, None, None),
        ),
    ],
)
def test_extract_job_details(url, controllers_info, expected):
    assert extract_job_details(url, controllers_info) == expected


def test_case_insensitive_match():
    # host is case insensitive
    result = extract_job_details(
        "HTTPS://CONTROLLER7.EXAMPLE.COM/jobs/playbook/654/",
        {"https://controller7.example.com": {"install_uuid": "uuid-8888"}},
    )
    assert result == ("run_job_template", "654", "uuid-8888")

    # path is case sensitive
    result = extract_job_details(
        "HTTPS://CONTROLLER7.EXAMPLE.COM/Jobs/Playbook/654/",
        {"https://controller7.example.com": {"install_uuid": "uuid-8888"}},
    )
    assert result == (None, None, None)


def test_partial_host_match():
    assert extract_job_details(
        "https://controller9.example.com/api/v2/jobs/playbook/777/",
        {"https://controller9.example.com": {"install_uuid": "uuid-9999"}},
    ) == ("run_job_template", "777", "uuid-9999")


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

    with mock.patch("aap_eda.analytics.utils.requests.get") as mock_get:
        mock_get.return_value = mock_resp
        data = collect_controllers_info()

        assert len(data.keys()) == 2
        assert default_host in data
        assert data[default_host]["install_uuid"] == install_uuid_1
        assert new_host in data
        assert data[new_host]["install_uuid"] == install_uuid_2


def test_yaml_error_handling():
    mock_credential = mock.MagicMock()
    mock_credential.id = 1
    mock_credential.inputs.get_secret_value.return_value = """
    host: https://test
    verify_ssl: True
    oauth_token: [invalid yaml
    """

    with mock.patch(
        "aap_eda.analytics.utils.models.CredentialType.objects.get"
    ), mock.patch(
        "aap_eda.analytics.utils.models.EdaCredential.objects.filter",
        return_value=[mock_credential],
    ), mock.patch(
        "aap_eda.analytics.utils.logger.error"
    ) as mock_logger:
        result = collect_controllers_info()
        assert result == {}
        args, _ = mock_logger.call_args
        assert args[0].startswith("YAML parsing error for credential 1: ")


@pytest.mark.parametrize(
    "error_input,error_msg",
    [
        (
            yaml.dump({"verify_ssl": "True", "oauth_token": "token"}),
            "Missing key in credential inputs: 'host'",
        ),
        (
            yaml.dump({"host": "https://test", "auth": {"type": "basic"}}),
            "Unexpected error processing credential 1: "
            "Invalid authentication configuration, must provide "
            "Token or username/password",
        ),
    ],
)
def test_key_error_handling(error_input, error_msg):
    mock_credential = mock.MagicMock()
    mock_credential.id = 1
    mock_credential.inputs.get_secret_value.return_value = error_input

    with mock.patch(
        "aap_eda.analytics.utils.models.CredentialType.objects.get"
    ), mock.patch(
        "aap_eda.analytics.utils.models.EdaCredential.objects.filter",
        return_value=[mock_credential],
    ), mock.patch(
        "aap_eda.analytics.utils.logger.error"
    ) as mock_logger:
        result = collect_controllers_info()
        assert result == {}
        if error_msg.startswith("Unexpected error"):
            mock_logger.assert_called_with(f"{error_msg}", exc_info=True)
        else:
            mock_logger.assert_called_with(f"{error_msg}")


@pytest.mark.parametrize(
    "exception_cls,log_level",
    [
        (RequestException, "warning"),
        (TimeoutError, "error"),
    ],
)
def test_request_exceptions(exception_cls, log_level):
    mock_credential = mock.MagicMock()
    mock_credential.id = 1
    mock_credential.name = "test_credential"
    mock_credential.inputs.get_secret_value.return_value = yaml.dump(
        {
            "host": "https://test",
            "verify_ssl": "True",
            "oauth_token": "valid_token",
        }
    )

    with mock.patch(
        "aap_eda.analytics.utils.models.CredentialType.objects.get"
    ), mock.patch(
        "aap_eda.analytics.utils.models.EdaCredential.objects.filter",
        return_value=[mock_credential],
    ), mock.patch(
        "aap_eda.analytics.utils.requests.get", side_effect=exception_cls
    ), mock.patch(
        f"aap_eda.analytics.utils.logger.{log_level}"
    ) as mock_logger:
        result = collect_controllers_info()
        assert result == {}
        if log_level == "warning":
            mock_logger.assert_called_with(
                "Controller connection failed for test_credential: "
                f"{exception_cls()}"
            )
        else:
            mock_logger.assert_called_with(
                f"Unexpected error processing credential 1: {exception_cls()}",
                exc_info=True,
            )


@pytest.mark.django_db
def test_mixed_success_and_failure():
    good_cred = mock.MagicMock()
    good_cred.id = 1
    good_cred.inputs.get_secret_value.return_value = yaml.dump(
        {
            "host": "https://good",
            "verify_ssl": "True",
            "oauth_token": "token",
        }
    )

    bad_cred = mock.MagicMock()
    bad_cred.id = 2
    bad_cred.inputs.get_secret_value.return_value = yaml.dump(
        {
            "host": "https://bad",
            "verify_ssl": "invalid",
        }
    )

    with mock.patch(
        "aap_eda.analytics.utils.models.CredentialType.objects.get"
    ), mock.patch(
        "aap_eda.analytics.utils.models.EdaCredential.objects.filter",
        return_value=[good_cred, bad_cred],
    ), mock.patch(
        "aap_eda.analytics.utils.requests.get"
    ) as mock_get, mock.patch(
        "aap_eda.analytics.utils.logger.error"
    ) as mock_logger:
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"install_uuid": "good_uuid"}
        mock_get.return_value = mock_response

        result = collect_controllers_info()
        assert list(result.keys()) == ["https://good"]
        mock_logger.assert_called_with(
            "Unexpected error processing credential 2: "
            "Invalid authentication configuration, must provide "
            "Token or username/password",
            exc_info=True,
        )


@pytest.mark.parametrize(
    "token,expected",
    [
        ("test_token", "Bearer test_token"),
        ("", "Bearer "),  # empty token
        ("special_chars_!@#$%^&*", "Bearer special_chars_!@#$%^&*"),
        ("12345", "Bearer 12345"),
    ],
)
def test_auth_header(basic_request, token, expected):
    auth = TokenAuth(token=token)

    modified_request = auth(basic_request.copy())

    assert modified_request.headers["Authorization"] == expected
    assert modified_request.headers["Content-Type"] == "application/json"
