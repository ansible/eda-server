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

import time
from unittest.mock import Mock, patch

import pytest

from aap_eda.conf import application_settings, settings_registry
from aap_eda.conf.registry import InvalidKeyError, InvalidValueError, logger

RESOURCE_SETTING = {
    "URL": "https://host",
    "SECRET_KEY": "secret",
    "VALIDATE_HTTPS": False,
}


@pytest.fixture(autouse=True)
def register() -> None:
    settings_registry.persist_registry_data()
    return None


@pytest.fixture
def eda_caplog(caplog_factory):
    return caplog_factory(logger)


@pytest.mark.django_db
def test_application_setting():
    application_settings.AUTOMATION_ANALYTICS_LAST_GATHER = "test"
    assert application_settings.AUTOMATION_ANALYTICS_LAST_GATHER == "test"


@pytest.mark.django_db
def test_non_application_setting():
    with pytest.raises(InvalidKeyError):
        application_settings.BAD_KEY


@pytest.mark.django_db
def test_read_only_application_setting():
    assert settings_registry.is_setting_read_only("REDHAT_USERNAME") is True
    assert settings_registry.is_setting_read_only("INSIGHTS_CERT_PATH") is True
    with pytest.raises(InvalidKeyError):
        application_settings.INSIGHTS_CERT_PATH = "path"


@pytest.mark.django_db
def test_application_setting_bad_type():
    assert (
        settings_registry.get_setting_type(
            "_GATEWAY_ANALYTICS_SETTING_SYNC_TIME"
        )
        == int
    )
    with pytest.raises(InvalidValueError):
        application_settings._GATEWAY_ANALYTICS_SETTING_SYNC_TIME = "bad_type"


@pytest.mark.django_db
def test_list_keys():
    assert len(settings_registry.get_registered_settings()) == 12


@pytest.mark.django_db
def test_read_remote_setting_no_resource_server(eda_caplog):
    assert application_settings.AUTOMATION_ANALYTICS_GATHER_INTERVAL == 14400
    assert "Skip resyncing remote settings" in eda_caplog.text


@pytest.mark.django_db
@patch("aap_eda.conf.registry.settings.RESOURCE_SERVER", RESOURCE_SETTING)
def test_read_remote_setting_with_api_exception(eda_caplog):
    assert application_settings.AUTOMATION_ANALYTICS_GATHER_INTERVAL == 14400
    assert (
        "Failed to fetch settings from gateway. Exception:" in eda_caplog.text
    )


@pytest.mark.django_db
@patch("aap_eda.conf.registry.settings.RESOURCE_SERVER", RESOURCE_SETTING)
def test_read_remote_setting_with_http_error(eda_caplog):
    mock_resp = Mock()
    mock_resp.status_code = 400
    mock_resp.ok = False
    with patch("aap_eda.analytics.utils.requests.get") as mock_get:
        mock_get.return_value = mock_resp
        assert (
            application_settings.AUTOMATION_ANALYTICS_GATHER_INTERVAL == 14400
        )
        assert (
            "Failed to fetch settings from gateway. HTTP status code 400"
            in eda_caplog.text
        )


@pytest.mark.django_db
@patch("aap_eda.conf.registry.settings.RESOURCE_SERVER", RESOURCE_SETTING)
@patch("aap_eda.conf.registry.RESYNC_INTERVAL", 1)
def test_read_remote_setting(eda_caplog):
    mock_resp = Mock()
    mock_resp.ok = True
    mock_resp.json.side_effect = [
        {
            "AUTOMATION_ANALYTICS_GATHER_INTERVAL": 500,
            "REDHAT_USERNAME": "foo",
        },
        {
            "AUTOMATION_ANALYTICS_GATHER_INTERVAL": 1000,
            "REDHAT_USERNAME": "bar",
        },
    ]

    with patch("aap_eda.analytics.utils.requests.get") as mock_get:
        mock_get.return_value = mock_resp
        assert application_settings.AUTOMATION_ANALYTICS_GATHER_INTERVAL == 500
        assert application_settings.REDHAT_USERNAME == "foo"
        # repeat within interval
        assert application_settings.AUTOMATION_ANALYTICS_GATHER_INTERVAL == 500
        assert application_settings.REDHAT_USERNAME == "foo"

        time.sleep(1)
        # repeat after interval
        assert (
            application_settings.AUTOMATION_ANALYTICS_GATHER_INTERVAL == 1000
        )
        assert application_settings.REDHAT_USERNAME == "bar"
