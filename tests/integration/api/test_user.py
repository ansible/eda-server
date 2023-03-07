#  Copyright 2023 Red Hat, Inc.
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

from aap_eda.core import models
from tests.integration.constants import api_url_v1


@pytest.fixture
def user() -> models.User:
    return models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )


@pytest.fixture
def client(base_client: APIClient, user: models.User) -> APIClient:
    client = base_client
    client.login(username=user.username, password="secret")
    return client


@pytest.mark.django_db
def test_retrieve_current_user(client: APIClient):
    response = client.get(f"{api_url_v1}/users/me/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "username": "luke.skywalker",
        "first_name": "Luke",
        "last_name": "Skywalker",
        "email": "luke.skywalker@example.com",
    }


@pytest.mark.django_db
def test_retrieve_current_user_unauthenticated(base_client: APIClient):
    client = base_client
    response = client.get(f"{api_url_v1}/users/me/")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }
