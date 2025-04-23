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
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from aap_eda.analytics.package import FailedToUploadPayload, Package
from aap_eda.utils import get_package_version

TEST_PASS = "test_pass"


@pytest.fixture
def package() -> Package:
    test_time = datetime(2023, 1, 1, 12, 30, 45, tzinfo=timezone.utc)
    mock_collector = MagicMock()
    mock_collector.gather_until = test_time

    return Package(collector=mock_collector)


@pytest.fixture
def mock_settings():
    class Settings:
        REDHAT_USERNAME = "test_user"
        REDHAT_PASSWORD = TEST_PASS
        AUTOMATION_ANALYTICS_URL = "https://test.url"

    return Settings()


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.headers = {}
    return session


@pytest.mark.django_db
def test_get_ingress_url(package: Package, mock_settings) -> None:
    mock_credentials = MagicMock()
    mock_credentials.return_value.exists.return_value = False

    with patch("aap_eda.analytics.utils.settings", new=mock_settings), patch(
        "aap_eda.analytics.utils._get_analytics_credentials",
        return_value=mock_credentials,
    ):
        assert package.get_ingress_url() == "https://test.url"


def test_shipping_auth_mode(package: Package) -> None:
    with patch(
        "django.conf.settings.AUTOMATION_AUTH_METHOD", new="test_auth_method"
    ):
        assert package.shipping_auth_mode() == "test_auth_method"


def test_tarname_base_timezone_handling(package: Package):
    result = package._tarname_base()

    assert "+0000" in result
    assert "eda-analytics-2023-01-01-123045+0000" == result


def test_get_http_request_headers(package: Package) -> None:
    headers = package._get_http_request_headers()
    assert headers["Content-Type"] == package.PAYLOAD_CONTENT_TYPE
    assert headers["User-Agent"] == package.USER_AGENT
    assert headers["X-EDA-Version"] == get_package_version("aap-eda")


@pytest.mark.django_db
def test_credential_priority(package, mock_settings):
    rh_user = "rh_user"
    rh_pass = "rh_pass"
    sub_user = "sub_user"
    sub_pass = "sub_pass"
    django_user = "django_user"
    django_pass = "django_pass"

    mock_settings.REDHAT_USERNAME = django_user
    mock_settings.REDHAT_PASSWORD = django_pass
    mock_settings.SUBSCRIPTIONS_USERNAME = sub_user
    mock_settings.SUBSCRIPTIONS_PASSWORD = sub_pass

    mock_credentials = MagicMock()
    mock_credentials.return_value.exists.return_value = False

    with patch(
        "aap_eda.analytics.utils.application_settings", new=mock_settings
    ), patch(
        "aap_eda.analytics.utils._get_analytics_credentials",
        return_value=mock_credentials,
    ):
        with override_settings(
            REDHAT_USERNAME=rh_user,
            REDHAT_PASSWORD=rh_pass,
        ):
            # first try on REDHAT's
            assert package._get_rh_user() == rh_user
            assert package._get_rh_password() == rh_pass

        # then try on SUBSCRIPTIONS's
        mock_settings.REDHAT_USERNAME = None
        mock_settings.REDHAT_PASSWORD = None
        assert package._get_rh_user() == sub_user
        assert package._get_rh_password() == sub_pass


def test_service_account_auth_with_valid_token(package, mock_session):
    with patch.object(package, "shipping_auth_mode") as mock_auth_mode, patch(
        "aap_eda.analytics.utils.get_proxy_url"
    ) as mock_proxy, patch(
        "aap_eda.analytics.utils.get_cert_path"
    ) as mock_cert, patch(
        "aap_eda.analytics.utils.generate_token"
    ):
        mock_auth_mode.return_value = package.SHIPPING_AUTH_SERVICE_ACCOUNT
        package.token.is_expired = lambda: False
        mock_proxy.return_value = "https://proxy:8080"
        mock_cert.return_value = "/path/to/cert"
        mock_session.post.return_value.status_code = 201

        package._send_data("https://test.com", {}, mock_session)

        mock_session.post.assert_called_once_with(
            "https://test.com",
            files={},
            verify="/path/to/cert",
            proxies={"https": "https://proxy:8080"},
            headers={"authorization": "Bearer "},
            timeout=(31, 31),
        )


def test_service_account_auth_with_token_renewal(package, mock_session):
    with patch.object(package, "shipping_auth_mode") as mock_auth_mode, patch(
        "aap_eda.analytics.utils.generate_token"
    ) as mock_gen_token:
        mock_auth_mode.return_value = package.SHIPPING_AUTH_SERVICE_ACCOUNT
        package.token.is_expired = lambda: True
        new_token = MagicMock(access_token="new_token_123")
        mock_gen_token.return_value = new_token
        mock_session.post.return_value.status_code = 201

        package._send_data("https://test.com", {}, mock_session)

        assert package.token == new_token
        assert mock_session.headers["authorization"] == "Bearer new_token_123"


def test_userpass_auth(package, mock_session):
    with patch.object(
        package, "shipping_auth_mode"
    ) as mock_auth_mode, patch.object(
        package, "_get_rh_user"
    ) as mock_user, patch.object(
        package, "_get_rh_password"
    ) as mock_pass, patch(
        "aap_eda.analytics.utils.get_cert_path"
    ) as mock_cert:
        mock_auth_mode.return_value = package.SHIPPING_AUTH_USERPASS
        mock_user.return_value = "test_user"
        mock_pass.return_value = "test_pass"
        mock_cert.return_value = "/path/to/cert"
        mock_session.post.return_value.status_code = 201

        package._send_data("https://test.com", {}, mock_session)

        mock_session.post.assert_called_once_with(
            "https://test.com",
            files={},
            verify="/path/to/cert",
            auth=("test_user", "test_pass"),
            headers={},
            timeout=(31, 31),
        )


def test_unknown_auth_mode(package, mock_session):
    with patch.object(package, "shipping_auth_mode") as mock_auth_mode:
        mock_auth_mode.return_value = "UNKNOWN_AUTH"
        mock_session.post.return_value.status_code = 201

        package._send_data("https://test.com", {}, mock_session)

        mock_session.post.assert_called_once_with(
            "https://test.com", files={}, headers={}, timeout=(31, 31)
        )


@pytest.mark.django_db
def test_handle_failed_upload(package, mock_session):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_session.post.return_value = mock_response

    with patch.object(package, "shipping_auth_mode") as mock_auth_mode:
        mock_auth_mode.return_value = "UNKNOWN_AUTH"

        with pytest.raises(FailedToUploadPayload) as exc_info:
            package._send_data("https://test.com", {}, mock_session)

        assert "status 400" in str(exc_info.value)
        assert "Bad Request" in str(exc_info.value)
