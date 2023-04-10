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

import pytest
from rest_framework import status
from rest_framework.test import APIClient, RequestsClient

from aap_eda.core import models
from tests.integration.constants import api_url_v1

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


@dataclass
class InitData:
    role: models.Role
    permisson: models.Permission


auth_url = f"http://testserver{api_url_v1}/auth/session"
login_url = f"{auth_url}/login/"
logout_url = f"{auth_url}/logout/"


@pytest.fixture
def user() -> models.User:
    return models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )


@pytest.fixture(scope="module")
def live_server(live_server):
    return live_server


def test_session_login_logout(live_server, user: models.User):
    client = RequestsClient()
    response = client.get(login_url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    csrf_token = response.cookies["csrftoken"]

    response = client.post(
        login_url,
        headers={
            "X-CSRFToken": csrf_token,
        },
        json={
            "username": "luke.skywalker",
            "password": "secret",
        },
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.text == ""
    assert "sessionid" in response.cookies
    csrf_token = response.cookies["csrftoken"]

    response = client.post(
        logout_url,
        headers={
            "X-CSRFToken": csrf_token,
        },
    )
    assert response.text == ""
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_session_login_invalid_credentials(
    base_client: APIClient, user: models.User
):
    response = base_client.post(
        login_url,
        data={
            "username": "luke.skywalker",
            "password": "invalid",
        },
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {
        "detail": "Invalid credentials or user is disabled."
    }


@pytest.mark.django_db
def test_logout_unauthenticated(base_client: APIClient):
    response = base_client.post(logout_url)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


def _get_crsf_token(client: RequestsClient):
    response = client.get(login_url)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    return response.cookies["csrftoken"]


# -----------------------------------------------------
# Roles
# -----------------------------------------------------
@pytest.mark.django_db
def test_list_roles(client: APIClient, init_db):
    response = client.get(f"{api_url_v1}/roles/")
    assert response.status_code == status.HTTP_200_OK
    roles = response.json()["results"]

    assert len(roles) == 1
    assert roles[0] == {
        "id": str(init_db.role.id),
        "name": init_db.role.name,
        "description": init_db.role.description,
    }


@pytest.mark.django_db
def test_retrieve_role(client: APIClient, init_db):
    test_uuid = init_db.role.id
    response = client.get(f"{api_url_v1}/roles/{test_uuid}/")
    assert response.status_code == status.HTTP_200_OK
    role = response.json()

    assert role == {
        "id": str(init_db.role.id),
        "name": init_db.role.name,
        "description": init_db.role.description,
        "permissions": [
            {"resource_type": "activation", "action": ["read", "write"]},
            {"resource_type": "user", "action": ["read"]},
        ],
        "created_at": init_db.role.created_at.strftime(DATETIME_FORMAT),
        "modified_at": init_db.role.modified_at.strftime(DATETIME_FORMAT),
    }


def init_role():
    roles = models.Role.objects.create(
        id=uuid.uuid4(),
        name="Test Role",
        description="testing role",
        is_default=False,
    )
    return roles


def init_permissions():
    permissions = models.Permission.objects.bulk_create(
        [
            models.Permission(
                id=uuid.uuid4(),
                resource_type="activation",
                action="read",
            ),
            models.Permission(
                id=uuid.uuid4(),
                resource_type="activation",
                action="write",
            ),
            models.Permission(
                id=uuid.uuid4(),
                resource_type="user",
                action="read",
            ),
        ]
    )

    return permissions


def init_role_permissions(role_data, permission_data, user: models.User):
    role_data.permissions.set(list(permission_data))
    role_data.users.add(user)


@pytest.fixture
def init_db(user: models.User):
    permissions = init_permissions()
    role = init_role()
    init_role_permissions(role, permissions, user)

    return InitData(
        role=role,
        permisson=permissions,
    )
