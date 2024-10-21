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
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.conf import settings_registry
from tests.integration.constants import api_url_v1


@pytest.fixture(autouse=True)
def register() -> None:
    settings_registry.persist_registry_data()


@pytest.mark.django_db
def test_list_system_settings(superuser_client: APIClient):
    response = superuser_client.get(f"{api_url_v1}/settings/system/")
    assert response.status_code == status.HTTP_200_OK
    data = response.data
    assert len(data) == 10
    assert data["INSIGHTS_TRACKING_STATE"] is False
    assert data["AUTOMATION_ANALYTICS_GATHER_INTERVAL"] == 14400


@pytest.mark.django_db
def test_partial_update_system_settings(superuser_client: APIClient):
    pword = "secret"
    body = {"REDHAT_USERNAME": "auser", "REDHAT_PASSWORD": pword}
    response = superuser_client.patch(
        f"{api_url_v1}/settings/system/", data=body
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.data
    assert len(data) == 10
    assert data["REDHAT_USERNAME"] == "auser"
    assert data["REDHAT_PASSWORD"] == "$encrypted$"


@pytest.mark.django_db
def test_list_settings_forbidden(user_client: APIClient):
    response = user_client.get(f"{api_url_v1}/settings/system/")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_update_settings_forbidden(user_client: APIClient):
    response = user_client.patch(f"{api_url_v1}/settings/system/", data={})
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_update_settings_wrong_type(superuser_client: APIClient):
    data = {"AUTOMATION_ANALYTICS_GATHER_INTERVAL": "not number"}
    response = superuser_client.patch(
        f"{api_url_v1}/settings/system/", data=data
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
