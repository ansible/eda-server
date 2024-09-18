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
from aap_eda.conf.registry import InvalidKeyError


@pytest.fixture(autouse=True)
def register() -> None:
    settings_registry.persist_registry_data()
    return None


@pytest.mark.django_db
def test_application_setting():
    application_settings.REDHAT_USERNAME = "test"
    assert application_settings.REDHAT_USERNAME == "test"


@pytest.mark.django_db
def test_non_application_setting():
    with pytest.raises(InvalidKeyError):
        application_settings.BAD_KEY


@pytest.mark.django_db
def test_read_only_application_setting():
    assert settings_registry.is_setting_read_only("INSIGHTS_CERT_PATH") is True
    with pytest.raises(InvalidKeyError):
        application_settings.INSIGHTS_CERT_PATH = "path"


@pytest.mark.django_db
def test_list_keys():
    assert len(settings_registry.get_registered_settings()) == 10


@pytest.mark.django_db
def test_db_update_and_display():
    assert settings_registry.is_setting_secret("REDHAT_PASSWORD") is True
    pwval = "secret"
    settings_registry.db_update_settings(
        {"REDHAT_USERNAME": "me", "REDHAT_PASSWORD": pwval}
    )
    settings = settings_registry.db_get_settings_for_display()
    assert settings["REDHAT_USERNAME"] == "me"
    assert settings["REDHAT_PASSWORD"] == "$encrypted$"
    assert application_settings.REDHAT_PASSWORD == pwval
