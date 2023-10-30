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
from typing import Any, Dict

import pytest
from django.db import connection
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
def test_create_controller_token(client: APIClient, user: models.User):
    response = client.post(
        f"{api_url_v1}/users/me/awx-tokens/",
        data={
            "name": "Test token 1",
            "token": "test-token-value",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "Test token 1"
    assert data["description"] == ""
    assert data["user_id"] == user.id
    assert "token" not in data

    obj = models.AwxToken.objects.get(pk=data["id"])
    assert obj.token.get_secret_value() == "test-token-value"
    assert_token_data(data, obj)

    with connection.cursor() as cursor:
        cursor.execute("SELECT token FROM core_awxtoken WHERE id = %s", (obj.id,))
        row = cursor.fetchone()
        assert row[0].startswith("$encrypted$fernet-256$")

    response = client.post(
        f"{api_url_v1}/users/me/awx-tokens/",
        data={
            "name": "Test token 2",
            "description": "Token description",
            "token": "test-token-value",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "Test token 2"
    assert data["description"] == "Token description"
    assert data["user_id"] == user.id
    assert "token" not in data


@pytest.mark.django_db
def test_create_token_missing_field(client: APIClient, user: models.User):
    response = client.post(
        f"{api_url_v1}/users/me/awx-tokens/",
        data={
            "token": "test-token-value",
        },
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "name": ["This field is required."],
    }

    response = client.post(
        f"{api_url_v1}/users/me/awx-tokens/",
        data={
            "name": "test-token",
        },
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "token": ["This field is required."],
    }


@pytest.mark.django_db(transaction=True)
def test_create_token_duplicate_name(client: APIClient, user: models.User):
    models.AwxToken.objects.create(user=user, name="test-token", token="test-token-value")

    response = client.post(
        f"{api_url_v1}/users/me/awx-tokens/",
        data={
            "name": "test-token",
            "token": "test-token-value",
        },
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "Token with this name already exists."}


@pytest.mark.django_db
def test_list_controller_tokens(client: APIClient, user: models.User):
    tokens = models.AwxToken.objects.bulk_create(
        [
            models.AwxToken(name="token-01", token="token-value-01", user=user),
            models.AwxToken(name="token-02", token="token-value-02", user=user),
        ]
    )
    response = client.get(f"{api_url_v1}/users/me/awx-tokens/")
    data = response.json()
    assert data["count"] == 2
    for token_response, token_db in zip(data["results"], tokens):
        assert_token_data(token_response, token_db)


@pytest.mark.django_db
def test_retrieve_controller_token(client: APIClient, user: models.User):
    obj = models.AwxToken.objects.create(name="token-01", token="token-value-01", user=user)
    response = client.get(f"{api_url_v1}/users/me/awx-tokens/{obj.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert_token_data(response.json(), obj)


@pytest.mark.django_db
def test_retrieve_controller_token_not_found(client: APIClient, user: models.User):
    response = client.get(f"{api_url_v1}/users/me/awx-tokens/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_delete_controller_token(client: APIClient, user: models.User):
    obj = models.AwxToken.objects.create(name="token-01", token="token-value-01", user=user)
    response = client.delete(f"{api_url_v1}/users/me/awx-tokens/{obj.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    exists = models.AwxToken.objects.filter(id=obj.id).exists()
    assert not exists


@pytest.mark.django_db
def test_delete_controller_token_not_found(client: APIClient, user: models.User):
    response = client.delete(f"{api_url_v1}/users/me/awx-tokens/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# Utils
# -------------------------------------
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def assert_token_data(data: Dict[str, Any], token: models.AwxToken):
    assert data == {
        "id": token.id,
        "name": token.name,
        "user_id": token.user_id,
        "description": token.description,
        "created_at": token.created_at.strftime(DATETIME_FORMAT),
        "modified_at": token.modified_at.strftime(DATETIME_FORMAT),
    }
