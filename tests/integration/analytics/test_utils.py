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
import time
import uuid
from datetime import datetime
from typing import List
from unittest import mock

import pytest
import yaml
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from requests import Request
from requests.exceptions import RequestException, SSLError, Timeout

from aap_eda.analytics.utils import (
    MissingUserPasswordError,
    ServiceToken,
    TokenAuth,
    _get_analytics_credentials,
    _get_credential_value,
    _validate_credential,
    collect_controllers_info,
    datetime_hook,
    extract_job_details,
    generate_token,
    get_analytics_interval,
    get_analytics_interval_if_exist,
    get_auth_mode,
    get_cert_path,
    get_client_id,
    get_client_secret,
    get_insights_tracking_state,
    get_oidc_token_url,
    get_proxy_url,
)
from aap_eda.core import models


@pytest.fixture
def basic_request():
    return Request(
        method="GET",
        url="https://example.com",
        headers={"Content-Type": "application/json"},
    ).prepare()


@pytest.fixture
def mock_oidc_config():
    with mock.patch(
        "aap_eda.analytics.utils.get_oidc_token_url"
    ) as mock_url, mock.patch(
        "aap_eda.analytics.utils.get_client_id"
    ) as mock_id, mock.patch(
        "aap_eda.analytics.utils.get_client_secret"
    ) as mock_secret, mock.patch(
        "aap_eda.analytics.utils.get_cert_path"
    ) as mock_cert:
        mock_url.return_value = "https://oidc.example.com/token"
        mock_id.return_value = "test_client"
        mock_secret.return_value = "test_secret"
        mock_cert.return_value = "/path/to/cert"
        yield


@pytest.fixture
def mock_credentials():
    credential = mock.MagicMock()
    credential.inputs.get_secret_value.return_value = "encrypted_data"
    return [credential]


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


def test_generate_token_success(mock_oidc_config):
    with mock.patch("requests.post") as mock_post:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_response

        result = generate_token()

        assert isinstance(result, ServiceToken)
        assert result.access_token == "test_token"
        assert result.expires_in == 3600
        mock_post.assert_called_once_with(
            "https://oidc.example.com/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_id": "test_client",
                "client_secret": "test_secret",
                "grant_type": "client_credentials",
            },
            verify="/path/to/cert",
            timeout=(31, 31),
        )


def test_missing_oidc_configuration():
    with mock.patch(
        "aap_eda.analytics.utils.get_oidc_token_url", return_value=None
    ), mock.patch(
        "aap_eda.analytics.utils.get_client_id", return_value=None
    ), mock.patch(
        "aap_eda.analytics.utils.get_client_secret", return_value=None
    ):
        with pytest.raises(ValueError) as exc_info:
            generate_token()

        assert "Missing required OIDC configuration" in str(exc_info.value)


@pytest.mark.parametrize(
    "exception,expected_error",
    [
        (SSLError(), SSLError),
        (Timeout(), Timeout),
        (RequestException("Error"), RequestException),
    ],
)
def test_token_request_exceptions(mock_oidc_config, exception, expected_error):
    with mock.patch("requests.post", side_effect=exception) as mock_post:
        with pytest.raises(expected_error):
            generate_token()

        mock_post.assert_called_once()


def test_invalid_token_response(mock_oidc_config):
    with mock.patch("requests.post") as mock_post:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid": "data"}
        mock_post.return_value = mock_response

        result = generate_token()

        assert result.access_token == ""
        assert result.expires_in == 0


def test_http_error_response(mock_oidc_config):
    with mock.patch("requests.post") as mock_post:
        mock_response = mock.Mock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = RequestException(
            "Bad request"
        )
        mock_post.return_value = mock_response

        with pytest.raises(RequestException):
            generate_token()


@pytest.mark.parametrize(
    "expires_in, expected_expires_at",
    [
        (3600, 1000 + 3600),  # Normal case
        (0, 1000),  # Zero expiration time
        (-300, 1000 - 300),  # Negative expiration time
    ],
)
def test_expires_at_property(expires_in, expected_expires_at):
    with mock.patch("time.time") as mock_time:
        # Freeze initial time at 1000 seconds
        mock_time.return_value = 1000

        token = ServiceToken(expires_in=expires_in)

        assert token.expires_at == expected_expires_at


@pytest.mark.parametrize(
    "current_time, expires_in, expected",
    [
        # Not expired scenarios
        (1500, 600, False),
        (1599, 600, False),
        # Expired scenarios
        (1600, 600, True),
        (2000, 600, True),
        # Special cases
        (1000, 0, True),
        (900, -100, True),
    ],
)
def test_is_expired(current_time, expires_in, expected):
    """Test token expiration status under various time conditions."""
    with mock.patch("time.time") as mock_time:
        # Set initial creation time to 1000
        mock_time.return_value = 1000
        token = ServiceToken(expires_in=expires_in)

        # Simulate current time check
        mock_time.return_value = current_time

        assert token.is_expired() == expected


def test_real_time_expiration():
    token = ServiceToken(expires_in=1)
    assert (
        not token.is_expired()
    ), "Token should be valid immediately after creation"

    # Wait just over the expiration threshold
    time.sleep(1.1)
    assert token.is_expired(), "Token should expire after 1 second"


def test_get_credential_from_store(mock_credentials):
    """Test credential retrieval from credential store."""
    with mock.patch(
        "aap_eda.analytics.utils._get_analytics_credentials"
    ) as mock_get_creds:
        mock_get_creds.return_value = mock_credentials
        with mock.patch(
            "aap_eda.analytics.utils.inputs_from_store"
        ) as mock_inputs:
            mock_inputs.return_value = {"client_id": "test_id"}

            result = _get_credential_value(
                "client_id",
                (settings, "REDHAT_USERNAME"),
                (settings, "REDHAT_PASSWORD"),
            )

            assert result == "test_id"


def test_get_from_settings():
    """Test fallback to Django settings when no credentials found."""
    with mock.patch(
        "aap_eda.analytics.utils._get_analytics_credentials"
    ) as mock_get_creds:
        mock_get_creds.return_value = []
        with mock.patch.object(settings, "REDHAT_USERNAME", "setting_user"):
            result = _get_credential_value(
                "username",
                (settings, "REDHAT_USERNAME"),
                (settings, "REDHAT_PASSWORD"),
            )

            assert result == "setting_user"


def test_multiple_setting_sources():
    """Test priority of multiple setting sources."""
    with mock.patch(
        "aap_eda.analytics.utils._get_analytics_credentials"
    ) as mock_get_creds:
        mock_get_creds.return_value = []
        with mock.patch.object(settings, "REDHAT_USERNAME", "first_user"):
            result = _get_credential_value(
                "username",
                (settings, "REDHAT_USERNAME"),
                (settings, "SUBSCRIPTIONS_USERNAME"),
            )

            assert result == "first_user"


def test_missing_value_returns_empty():
    """Test missing value returns empty string."""
    with mock.patch(
        "aap_eda.analytics.utils._get_analytics_credentials"
    ) as mock_get_creds:
        mock_get_creds.return_value = []

        result = _get_credential_value(
            "missing_field",
            (settings, "NON_EXISTENT_SETTING"),
        )

        assert result is None


def test_get_cert_path():
    """Test INSIGHTS_CERT_PATH retrieval."""
    with mock.patch.object(settings, "INSIGHTS_CERT_PATH", "/custom/path"):
        assert get_cert_path() == "/custom/path"


def test_get_auth_mode():
    """Test AUTOMATION_AUTH_METHOD retrieval."""
    with mock.patch.object(settings, "AUTOMATION_AUTH_METHOD", "oidc"):
        assert get_auth_mode() == "oidc"


def test_get_oidc_token_url():
    """Test AUTOMATION_ANALYTICS_OIDC_TOKEN_URL retrieval."""
    with mock.patch.object(
        settings,
        "AUTOMATION_ANALYTICS_OIDC_TOKEN_URL",
        "https://oidc.example.com",
    ):
        assert get_oidc_token_url() == "https://oidc.example.com"


def test_get_proxy_url():
    """Test ANALYTICS_PROXY_URL retrieval."""
    with mock.patch.object(
        settings, "ANALYTICS_PROXY_URL", "https://proxy:8080"
    ):
        assert get_proxy_url() == "https://proxy:8080"


def test_get_insights_tracking_state():
    with mock.patch(
        "aap_eda.analytics.utils._get_credential_value"
    ) as mock_get:
        mock_get.return_value = True
        assert get_insights_tracking_state() is True


def test_get_client_id():
    """Test client ID retrieval."""
    with mock.patch(
        "aap_eda.analytics.utils._get_credential_value"
    ) as mock_get_value:
        mock_get_value.return_value = "test_client_id"
        assert get_client_id() == "test_client_id"
        mock_get_value.assert_called_once_with("client_id")


def test_get_client_secret():
    """Test client secret retrieval."""
    with mock.patch(
        "aap_eda.analytics.utils._get_credential_value"
    ) as mock_get_value:
        mock_get_value.return_value = "test_secret"
        assert get_client_secret() == "test_secret"
        mock_get_value.assert_called_once_with("client_secret")


def test_get_analytics_interval_valid_conversion():
    with mock.patch(
        "aap_eda.analytics.utils._get_credential_value"
    ) as mock_get:
        mock_get.return_value = "300"
        assert get_analytics_interval() == 300


def test_get_analytics_interval_invalid_fallback():
    with mock.patch(
        "aap_eda.analytics.utils._get_credential_value"
    ) as mock_get:
        mock_get.return_value = "invalid"
        result = get_analytics_interval()
        assert isinstance(result, int)


@pytest.mark.parametrize(
    "cred_kind, expected",
    [("analytics", 300), ("other", 0)],
)
@pytest.mark.django_db
def test_get_analytics_interval_if_exists(cred_kind, expected):
    mock_cred_type = mock.MagicMock(spec=models.CredentialType)
    mock_cred_type.kind = cred_kind

    mock_credential = mock.MagicMock(spec=models.EdaCredential)
    mock_credential.credential_type = mock_cred_type
    mock_credential.inputs.get_secret_value.return_value = (
        "gather_interval: 300"
    )

    with mock.patch(
        "aap_eda.analytics.utils.get_auth_mode", return_value="analytics"
    ):
        assert get_analytics_interval_if_exist(mock_credential) == expected


def test_validate_credential_with_existing_credentials():
    with mock.patch(
        "aap_eda.analytics.utils._get_analytics_credentials"
    ) as mock_creds:
        mock_creds.return_value.exists.return_value = True
        _validate_credential()


@pytest.mark.django_db
def test_validate_credential_with_settings_credentials():
    with mock.patch(
        "aap_eda.analytics.utils._get_analytics_credentials"
    ) as mock_creds, mock.patch(
        "aap_eda.analytics.utils.settings"
    ) as mock_settings:
        data = "pass"
        mock_creds.return_value.exists.return_value = False
        mock_settings.REDHAT_USERNAME = "user"
        mock_settings.REDHAT_PASSWORD = data
        _validate_credential()


def test_validate_credential_error_handling():
    mock_app_settings = mock.MagicMock()
    mock_app_settings.configure_mock(
        SUBSCRIPTIONS_USERNAME=None,
        SUBSCRIPTIONS_PASSWORD=None,
        REDHAT_USERNAME=None,
        REDHAT_PASSWORD=None,
    )

    mock_django_settings = mock.MagicMock()
    mock_django_settings.configure_mock(
        REDHAT_USERNAME=None,
        REDHAT_PASSWORD=None,
        SUBSCRIPTIONS_USERNAME=None,
        SUBSCRIPTIONS_PASSWORD=None,
    )

    with mock.patch(
        "aap_eda.analytics.utils._get_analytics_credentials"
    ) as mock_creds, mock.patch(
        "aap_eda.analytics.utils.settings", mock_django_settings
    ), mock.patch(
        "aap_eda.analytics.utils.application_settings", mock_app_settings
    ), mock.patch(
        "aap_eda.analytics.utils.logger.error"
    ) as mock_logger:
        mock_creds.return_value.exists.return_value = False

        with pytest.raises(MissingUserPasswordError) as exc_info:
            _validate_credential()

        mock_logger.assert_called_once_with(
            "Missing required credentials in settings"
        )
        assert "Valid credentials not found" in str(exc_info.value)


@pytest.mark.django_db
def test_get_analytics_credentials():
    mock_cred_type = mock.MagicMock(spec=models.CredentialType)
    mock_cred_type.kind = "test_auth_mode"

    mock_credential = mock.MagicMock(spec=models.EdaCredential)
    mock_credential.credential_type = mock_cred_type

    with mock.patch(
        "aap_eda.analytics.utils.get_auth_mode", return_value="test_auth_mode"
    ), mock.patch.object(
        models.CredentialType.objects, "filter"
    ) as mock_type_filter, mock.patch.object(
        models.EdaCredential.objects, "filter"
    ) as mock_cred_filter:
        mock_type_filter.return_value = [mock_cred_type]
        mock_cred_filter.return_value = [mock_credential]

        credentials = _get_analytics_credentials()

        mock_type_filter.assert_called_once_with(kind="test_auth_mode")
        mock_cred_filter.assert_called_once_with(
            credential_type__in=[mock_cred_type]
        )

        assert credentials == [mock_credential]
