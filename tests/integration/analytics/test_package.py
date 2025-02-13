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

from aap_eda.analytics.package import MissingUserPasswordError, Package

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


@pytest.mark.django_db
def test_get_ingress_url(package: Package, mock_settings) -> None:
    with patch(
        "aap_eda.analytics.package.application_settings",
        new=mock_settings,
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

    with patch.dict("django.conf.settings.__dict__", {"EDA_VERSION": "1.0.0"}):
        headers = package._get_http_request_headers()
        assert headers["X-EDA-Version"] == "1.0.0"


@pytest.mark.parametrize(
    "app_settings, django_settings, should_raise",
    [
        # no credentials
        ({"REDHAT_USERNAME": None, "REDHAT_PASSWORD": None}, {}, True),
        # credentials in application_settings
        ({"REDHAT_USERNAME": "user", "REDHAT_PASSWORD": TEST_PASS}, {}, False),
        # credentials in django_settings
        (
            {"REDHAT_USERNAME": None, "REDHAT_PASSWORD": None},
            {"REDHAT_USERNAME": "user", "REDHAT_PASSWORD": TEST_PASS},
            False,
        ),
        # mixed with valid a credential
        (
            {"REDHAT_USERNAME": "user1", "REDHAT_PASSWORD": None},
            {"REDHAT_USERNAME": "user2", "REDHAT_PASSWORD": TEST_PASS},
            False,
        ),
        # mixed without valid credentials
        (
            {"REDHAT_USERNAME": "user", "REDHAT_PASSWORD": None},
            {"REDHAT_USERNAME": None, "REDHAT_PASSWORD": TEST_PASS},
            True,
        ),
    ],
)
@pytest.mark.django_db
def test_check_users_credentials(
    package,
    mock_settings,
    app_settings,
    django_settings,
    should_raise,
):
    mock_settings.REDHAT_USERNAME = app_settings["REDHAT_USERNAME"]
    mock_settings.REDHAT_PASSWORD = app_settings["REDHAT_PASSWORD"]
    with patch(
        "aap_eda.analytics.package.application_settings", new=mock_settings
    ):
        with override_settings(**django_settings):
            if should_raise:
                with pytest.raises(MissingUserPasswordError) as exc_info:
                    package._check_users()
                assert "Valid user credentials not found" in str(
                    exc_info.value
                )
            else:
                package._check_users()


def test_credential_priority(package, mock_settings):
    rh_pass = "app_rh_pass"
    sub_pass = "app_sub_pass"
    django_rh_pass = "django_rh_pass"

    mock_settings.REDHAT_USERNAME = "app_rh_user"
    mock_settings.SUBSCRIPTIONS_USERNAME = "app_sub_user"
    mock_settings.REDHAT_PASSWORD = rh_pass
    mock_settings.SUBSCRIPTIONS_PASSWORD = sub_pass

    with patch(
        "aap_eda.analytics.package.application_settings", new=mock_settings
    ):
        with override_settings(
            REDHAT_USERNAME="django_rh_user",
            REDHAT_PASSWORD=django_rh_pass,
        ):
            # first try on REDHAT's
            assert package._get_rh_user() == "django_rh_user"
            assert package._get_rh_password() == "django_rh_pass"

        # then try on SUBSCRIPTIONS's
        mock_settings.REDHAT_USERNAME = None
        mock_settings.REDHAT_PASSWORD = None
        assert package._get_rh_user() == "app_sub_user"
        assert package._get_rh_password() == "app_sub_pass"
