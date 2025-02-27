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

from aap_eda.analytics.package import Package
from aap_eda.utils import get_eda_version

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
        "aap_eda.analytics.utils.application_settings", new=mock_settings
    ), patch(
        "aap_eda.analytics.utils._get_analytics_credential",
        return_value=None,
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
    assert headers["X-EDA-Version"] == get_eda_version()


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

    with patch(
        "aap_eda.analytics.utils.application_settings", new=mock_settings
    ), patch(
        "aap_eda.analytics.utils._get_analytics_credential", return_value=None
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
