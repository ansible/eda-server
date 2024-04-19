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
from ansible_base.rbac.models import RoleDefinition
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.constants import api_url_v1

from .conftest import ADMIN_USERNAME

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


@pytest.fixture
def super_user():
    return models.User.objects.create(username="super-user", is_superuser=True)


@pytest.fixture
def random_user():
    return models.User.objects.create(username="unprivledged-user")


@pytest.fixture
def admin_api_client(super_user):
    client = APIClient()
    client.force_authenticate(user=super_user)
    return client


@pytest.fixture
def user_api_client(random_user):
    client = APIClient()
    client.force_authenticate(user=random_user)
    return client


@pytest.fixture
def org_admin_rd():
    return RoleDefinition.objects.create_from_permissions(
        name="organization-admin",
        permissions=[
            "change_organization",
            "view_organization",
            "delete_organization",
        ],
        content_type=ContentType.objects.get_for_model(models.Organization),
    )


@pytest.mark.django_db
def test_retrieve_current_user(client: APIClient, admin_user: models.User):
    response = client.get(f"{api_url_v1}/users/me/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "id": admin_user.id,
        "username": admin_user.username,
        "first_name": admin_user.first_name,
        "last_name": admin_user.last_name,
        "email": admin_user.email,
        "is_superuser": admin_user.is_superuser,
        "resource": {
            "ansible_id": str(admin_user.resource.ansible_id),
            "resource_type": admin_user.resource.resource_type,
        },
        "created_at": admin_user.date_joined.strftime(DATETIME_FORMAT),
        "modified_at": admin_user.modified_at.strftime(DATETIME_FORMAT),
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
def test_update_current_user(client: APIClient, admin_user: models.User):
    response = client.patch(
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
    client: APIClient, admin_user: models.User
):
    response = client.patch(
        f"{api_url_v1}/users/me/",
        data={"password": "updated-password"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "password" not in data

    admin_user.refresh_from_db()
    assert admin_user.check_password("updated-password")


@pytest.mark.django_db
def test_update_current_user_username_fail(
    client: APIClient, admin_user: models.User
):
    response = client.patch(
        f"{api_url_v1}/users/me/",
        data={"username": "darth.vader"},
    )
    # NOTE(cutwater): DRF serializer will not detect an unexpected field
    #   in PATCH operation, but must ignore it.
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["username"] == admin_user.username

    admin_user.refresh_from_db()
    assert admin_user.username == ADMIN_USERNAME


@pytest.mark.django_db
def test_create_user(client: APIClient):
    create_user_data = {
        "username": "test.user",
        "first_name": "Test",
        "last_name": "User",
        "email": "test.user@example.com",
        "password": "secret",
    }

    response = client.post(f"{api_url_v1}/users/", data=create_user_data)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["is_superuser"] is False


@pytest.mark.django_db
def test_create_superuser(
    admin_api_client: APIClient,
    user_api_client: APIClient,
    org_admin_rd,
    random_user,
):
    create_user_data = {
        "username": "test.user",
        "first_name": "Test",
        "last_name": "User",
        "email": "test.user@example.com",
        "password": "secret",
        "is_superuser": True,
    }

    response = admin_api_client.post(
        f"{api_url_v1}/users/", data=create_user_data
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["is_superuser"] is True
    create_user_data["username"] += "-2"  # avoid integrity errors

    response = user_api_client.post(
        f"{api_url_v1}/users/", data=create_user_data
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Even if user is org admin, would NORMALLY have permission
    # this should still be denied because it is creating a superuser
    org = models.Organization.objects.first()
    org_admin_rd.give_permission(random_user, org)
    response = user_api_client.post(
        f"{api_url_v1}/users/", data=create_user_data
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_organization_admin_can_create_user(
    random_user, user_api_client, org_admin_rd
):
    create_user_data = {
        "username": "test.user",
        "first_name": "Test",
        "last_name": "User",
        "email": "test.user@example.com",
        "password": "secret",
        "is_superuser": False,
    }
    org = models.Organization.objects.first()
    org_admin_rd.give_permission(random_user, org)
    response = user_api_client.post(
        f"{api_url_v1}/users/", data=create_user_data
    )
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_retrieve_user_details(
    admin_api_client: APIClient,
    user_api_client: APIClient,
    default_user: models.User,
):
    response = admin_api_client.get(f"{api_url_v1}/users/{default_user.id}/")
    assert response.status_code == status.HTTP_200_OK
    response_data = response.data.copy()
    response_data.pop("resource", None)
    assert response_data == {
        "id": default_user.id,
        "username": default_user.username,
        "first_name": default_user.first_name,
        "last_name": default_user.last_name,
        "email": default_user.email,
        "is_superuser": default_user.is_superuser,
        "created_at": default_user.date_joined.strftime(DATETIME_FORMAT),
        "modified_at": default_user.modified_at.strftime(DATETIME_FORMAT),
    }

    response = user_api_client.get(f"{api_url_v1}/users/{default_user.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_list_users(
    client: APIClient,
    admin_user: models.User,
):
    response = client.get(f"{api_url_v1}/users/")
    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]

    assert len(results) == 1
    assert results[0] == {
        "id": admin_user.id,
        "username": admin_user.username,
        "first_name": admin_user.first_name,
        "last_name": admin_user.last_name,
        "is_superuser": admin_user.is_superuser,
        "resource": {
            "ansible_id": str(admin_user.resource.ansible_id),
            "resource_type": admin_user.resource.resource_type,
        },
    }


@pytest.mark.django_db
def test_partial_update_user(
    client: APIClient,
    admin_user: models.User,
):
    data = {"first_name": "Anakin"}
    response = client.patch(f"{api_url_v1}/users/{admin_user.id}/", data=data)
    assert response.status_code == status.HTTP_200_OK

    updated_user = models.User.objects.get(id=admin_user.id)
    assert response.json() == {
        "id": updated_user.id,
        "username": updated_user.username,
        "first_name": updated_user.first_name,
        "last_name": updated_user.last_name,
        "email": updated_user.email,
        "is_superuser": admin_user.is_superuser,
        "resource": {
            "ansible_id": str(admin_user.resource.ansible_id),
            "resource_type": admin_user.resource.resource_type,
        },
        "created_at": updated_user.date_joined.strftime(DATETIME_FORMAT),
        "modified_at": updated_user.modified_at.strftime(DATETIME_FORMAT),
    }


@pytest.mark.django_db
def test_delete_user(
    client: APIClient,
    default_user: models.User,
):
    response = client.delete(f"{api_url_v1}/users/{default_user.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert models.User.objects.filter(id=default_user.id).count() == 0


@pytest.mark.django_db
def test_delete_user_not_allowed(
    client: APIClient,
    admin_user: models.User,
):
    response = client.delete(f"{api_url_v1}/users/{admin_user.id}/")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    assert models.User.objects.filter(id=admin_user.id).count() == 1


@pytest.mark.django_db
def test_list_users_filter_username(
    client: APIClient,
    admin_user: models.User,
    default_user: models.User,
):
    response = client.get(
        f"{api_url_v1}/users/?username={admin_user.username}"
    )
    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]

    assert len(results) == 1
    assert results[0] == {
        "id": admin_user.id,
        "username": admin_user.username,
        "first_name": admin_user.first_name,
        "last_name": admin_user.last_name,
        "is_superuser": admin_user.is_superuser,
        "resource": {
            "ansible_id": str(admin_user.resource.ansible_id),
            "resource_type": admin_user.resource.resource_type,
        },
    }


@pytest.mark.django_db
def test_list_users_filter_username_non_exist(
    client: APIClient,
    admin_user: models.User,
):
    response = client.get(f"{api_url_v1}/users/?username=test")
    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]

    assert len(results) == 0


@pytest.mark.django_db
def test_list_users_filter_by_ansible_id(
    client: APIClient,
    admin_user: models.User,
    default_user: models.User,
):
    filter = default_user.resource.ansible_id
    response = client.get(f"{api_url_v1}/users/?resource__ansible_id={filter}")
    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0] == {
        "id": default_user.id,
        "username": default_user.username,
        "first_name": default_user.first_name,
        "last_name": default_user.last_name,
        "is_superuser": default_user.is_superuser,
        "resource": {
            "ansible_id": str(default_user.resource.ansible_id),
            "resource_type": default_user.resource.resource_type,
        },
    }

    response = client.get(
        f"{api_url_v1}/users/?resource__ansible_id=non-existent-org"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 0
