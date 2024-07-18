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
import yaml
from django.conf import settings
from rest_framework import status

from tests.integration.constants import api_url_v1

OPENAPI_TITLE = settings.SPECTACULAR_SETTINGS["TITLE"]


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/openapi.json", id="openapi_json"),
        pytest.param("/openapi.yaml", id="openapi_yaml"),
    ],
)
@pytest.mark.django_db
def test_v1_openapi(admin_client, path):
    response = admin_client.get(f"{api_url_v1}{path}")
    assert response.status_code == status.HTTP_200_OK
    data = yaml.safe_load(response.content)
    assert data["info"]["title"] == OPENAPI_TITLE


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/docs/", id="swagger_ui"),
        pytest.param("/redoc/", id="redoc"),
    ],
)
def test_v1_openapi_ui(admin_client, path):
    response = admin_client.get(f"{api_url_v1}{path}")
    assert response.status_code == status.HTTP_200_OK
    assert OPENAPI_TITLE in response.content.decode()
