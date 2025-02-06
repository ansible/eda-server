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

import pytest

from aap_eda.conf import application_settings, settings_registry
from aap_eda.conf.registry import InvalidKeyError, InvalidValueError


@pytest.fixture(autouse=True)
def register() -> None:
    settings_registry.persist_registry_data()
    return None


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
