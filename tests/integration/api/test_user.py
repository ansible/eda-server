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
import uuid
from dataclasses import dataclass
from unittest import mock

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from aap_eda.core.enums import Action, ResourceType
from tests.integration.constants import api_url_v1

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


@dataclass
class InitData:
    role: models.Role


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
def user2() -> models.User:
    return models.User.objects.create_user(
        username="leia.organa",
        first_name="Leia",
        last_name="Organa",
        email="leia.organa@example.com",
        password="secret",
    )


@pytest.fixture
def api_client(base_client: APIClient, user: models.User) -> APIClient:
    client = base_client
    client.login(username=user.username, password="secret")
    return client


@pytest.mark.django_db
def test_retrieve_current_user(
    api_client: APIClient, user: models.User, init_db
):
    response = api_client.get(f"{api_url_v1}/users/me/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "is_superuser": user.is_superuser,
        "roles": [
            {
                "id": str(init_db.role.id),
                "name": init_db.role.name,
            }
        ],
        "created_at": user.date_joined.strftime(DATETIME_FORMAT),
        "modified_at": user.modified_at.strftime(DATETIME_FORMAT),
    }


@pytest.mark.django_db
def test_retrieve_current_user_unauthenticated(base_client: APIClient):
    client = base_client
    response = client.get(f"{api_url_v1}/users/me/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


@pytest.mark.django_db
def test_update_current_user(
    api_client: APIClient, user: models.User, init_db
):
    response = api_client.patch(
        f"{api_url_v1}/users/me/",
        data={
            "first_name": "Darth",
            "last_name": "Vader",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["first_name"] == "Darth"
    assert data["last_name"] == "Vader"


@pytest.mark.django_db
def test_update_current_user_password(
    api_client: APIClient, user: models.User, init_db
):
    response = api_client.patch(
        f"{api_url_v1}/users/me/",
        data={"password": "updated-password"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "password" not in data

    user.refresh_from_db()
    assert user.check_password("updated-password")


@pytest.mark.django_db
def test_update_current_user_username_fail(
    api_client: APIClient, user: models.User, init_db
):
    response = api_client.patch(
        f"{api_url_v1}/users/me/",
        data={"username": "darth.vader"},
    )
    # NOTE(cutwater): DRF serializer will not detect an unexpected field
    #   in PATCH operation, but must ignore it.
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["username"] == "luke.skywalker"

    user.refresh_from_db()
    assert user.username == "luke.skywalker"


@pytest.mark.django_db
def test_update_current_user_roles_fail(
    api_client: APIClient, user: models.User, init_db
):
    response = api_client.patch(f"{api_url_v1}/users/me/", data={"roles": []})
    # NOTE(cutwater): DRF serializer will not detect an unexpected field
    #   in PATCH operation, but must ignore it.
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["roles"]) > 0


@pytest.mark.django_db
def test_create_user(
    api_client: APIClient,
    check_permission_mock: mock.Mock,
    init_db,
):
    create_user_data = {
        "username": "test.user",
        "first_name": "Test",
        "last_name": "User",
        "email": "test.user@example.com",
        "password": "secret",
        "roles": [str(init_db.role.id)],
    }

    response = api_client.post(f"{api_url_v1}/users/", data=create_user_data)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["is_superuser"] is False
    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.USER, Action.CREATE
    )


@pytest.mark.django_db
def test_create_superuser(
    client: APIClient,
    check_permission_mock: mock.Mock,
    init_db,
):
    create_user_data = {
        "username": "test.user",
        "first_name": "Test",
        "last_name": "User",
        "email": "test.user@example.com",
        "password": "secret",
        "is_superuser": True,
        "roles": [str(init_db.role.id)],
    }

    response = client.post(f"{api_url_v1}/users/", data=create_user_data)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["is_superuser"] is True
    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.USER, Action.CREATE
    )


@pytest.mark.django_db
def test_retrieve_user_details(
    client: APIClient,
    user: models.User,
    init_db,
    check_permission_mock: mock.Mock,
):
    user_id = user.id
    response = client.get(f"{api_url_v1}/users/{user_id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "is_superuser": user.is_superuser,
        "roles": [
            {
                "id": str(init_db.role.id),
                "name": init_db.role.name,
            }
        ],
        "created_at": user.date_joined.strftime(DATETIME_FORMAT),
        "modified_at": user.modified_at.strftime(DATETIME_FORMAT),
    }

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.USER, Action.READ
    )


@pytest.mark.django_db
def test_list_users(
    api_client: APIClient,
    user: models.User,
    init_db,
    check_permission_mock: mock.Mock,
):
    response = api_client.get(f"{api_url_v1}/users/")
    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]

    assert len(results) == 1
    assert results[0] == {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_superuser": user.is_superuser,
        "roles": [
            {
                "id": str(init_db.role.id),
                "name": init_db.role.name,
            }
        ],
    }

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.USER, Action.READ
    )


@pytest.mark.django_db
def test_partial_update_user(
    client: APIClient,
    user: models.User,
    init_db,
    check_permission_mock: mock.Mock,
):
    user_id = user.id
    data = {"first_name": "Anakin"}
    response = client.patch(f"{api_url_v1}/users/{user_id}/", data=data)
    assert response.status_code == status.HTTP_200_OK

    updated_user = models.User.objects.get(id=user_id)
    assert response.json() == {
        "id": updated_user.id,
        "username": updated_user.username,
        "first_name": updated_user.first_name,
        "last_name": updated_user.last_name,
        "email": updated_user.email,
        "is_superuser": user.is_superuser,
        "roles": [
            {
                "id": str(init_db.role.id),
                "name": init_db.role.name,
            }
        ],
        "created_at": updated_user.date_joined.strftime(DATETIME_FORMAT),
        "modified_at": updated_user.modified_at.strftime(DATETIME_FORMAT),
    }

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.USER, Action.UPDATE
    )


@pytest.mark.django_db
def test_delete_user(
    client: APIClient,
    user2: models.User,
    check_permission_mock: mock.Mock,
):
    user_id = user2.id
    response = client.delete(f"{api_url_v1}/users/{user_id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert models.User.objects.filter(id=user_id).count() == 0

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.USER, Action.DELETE
    )


@pytest.mark.django_db
def test_delete_user_not_allowed(
    api_client: APIClient,
    user: models.User,
    check_permission_mock: mock.Mock,
):
    user_id = user.id
    response = api_client.delete(f"{api_url_v1}/users/{user_id}/")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    assert models.User.objects.filter(id=user_id).count() == 1

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.USER, Action.DELETE
    )


@pytest.mark.django_db
def test_list_users_filter_username(
    client: APIClient,
    user: models.User,
    user2: models.User,
    init_db,
    check_permission_mock: mock.Mock,
):
    response = client.get(f"{api_url_v1}/users/?username=luke.skywalker")
    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]

    assert len(results) == 1
    assert results[0] == {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_superuser": user.is_superuser,
        "roles": [
            {
                "id": str(init_db.role.id),
                "name": init_db.role.name,
            }
        ],
    }

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.USER, Action.READ
    )


@pytest.mark.django_db
def test_list_users_filter_username_non_exist(
    client: APIClient,
    user: models.User,
    user2: models.User,
    init_db,
    check_permission_mock: mock.Mock,
):
    response = client.get(f"{api_url_v1}/users/?username=test")
    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]

    assert len(results) == 0

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.USER, Action.READ
    )


def init_role():
    roles = models.Role.objects.create(
        id=uuid.uuid4(),
        name="Test Role",
        description="testing role",
        is_default=False,
    )
    return roles


def init_user_role(role, user: models.User):
    user.roles.add(role)


@pytest.fixture
def init_db(user: models.User):
    role = init_role()
    init_user_role(role, user)
    return InitData(
        role=role,
    )
