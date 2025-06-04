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
import secrets
from typing import Any, Dict

import pytest
from ansible_base.rbac.models import DABPermission, RoleDefinition
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from aap_eda.core import enums, models
from tests.integration.api.test_event_stream import (
    create_event_stream,
    create_event_stream_credential,
    get_default_test_org,
)
from tests.integration.constants import api_url_v1

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


@pytest.fixture
def user_api_client(default_user):
    admin_client = APIClient()
    admin_client.force_authenticate(user=default_user)
    return admin_client


@pytest.fixture
def org_admin_rd():
    return RoleDefinition.objects.create_from_permissions(
        name="organization-admin",
        permissions=[
            "change_organization",
            "member_organization",
            "view_organization",
            "delete_organization",
        ],
        content_type=ContentType.objects.get_for_model(models.Organization),
        managed=True,  # custom roles can not include these permissions
    )


@pytest.fixture
def org_member_rd():
    return RoleDefinition.objects.create_from_permissions(
        name="organization-member",
        permissions=[
            "member_organization",
            "view_organization",
        ],
        content_type=ContentType.objects.get_for_model(models.Organization),
        managed=True,
    )


@pytest.mark.django_db
def test_retrieve_current_user(
    admin_client: APIClient, admin_user: models.User
):
    response = admin_client.get(f"{api_url_v1}/users/me/")
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
    response = base_client.get(f"{api_url_v1}/users/me/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


@pytest.mark.django_db
def test_update_current_user(admin_client: APIClient, admin_user: models.User):
    response = admin_client.patch(
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
def test_update_current_user_forbidden(
    use_shared_resource_setting,
    admin_client: APIClient,
    admin_user: models.User,
):
    response = admin_client.patch(
        f"{api_url_v1}/users/me/",
        data={
            "first_name": "Darth",
            "last_name": "Vader",
        },
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_update_current_user_password(
    admin_client: APIClient, admin_user: models.User
):
    response = admin_client.patch(
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
    admin_client: APIClient,
    admin_user: models.User,
    admin_info: dict,
):
    response = admin_client.patch(
        f"{api_url_v1}/users/me/",
        data={"username": "darth.vader"},
    )
    # NOTE(cutwater): DRF serializer will not detect an unexpected field
    #   in PATCH operation, but must ignore it.
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["username"] == admin_user.username

    admin_user.refresh_from_db()
    assert admin_user.username == admin_info["username"]


@pytest.mark.django_db
def test_create_user(admin_client: APIClient):
    create_user_data = {
        "username": "test.user",
        "first_name": "Test",
        "last_name": "User",
        "email": "test.user@example.com",
        "password": "secret",
    }

    response = admin_client.post(f"{api_url_v1}/users/", data=create_user_data)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["is_superuser"] is False


@pytest.mark.django_db
def test_create_user_forbidden(
    use_shared_resource_setting, admin_client: APIClient
):
    create_user_data = {
        "username": "test.user",
        "first_name": "Test",
        "last_name": "User",
        "email": "test.user@example.com",
        "password": "secret",
    }

    response = admin_client.post(f"{api_url_v1}/users/", data=create_user_data)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_update_is_superuser_field(
    use_shared_resource_setting,
    superuser_client: APIClient,
    new_user: models.User,
):
    data = {"is_superuser": True}

    response = superuser_client.patch(
        f"{api_url_v1}/users/{new_user.id}/", data=data
    )
    assert response.status_code == status.HTTP_200_OK, response.data

    updated_user = models.User.objects.get(id=new_user.id)
    assert updated_user.is_superuser is True
    assert response.data["is_superuser"] == updated_user.is_superuser


@pytest.mark.django_db
def test_update_superuser_field_as_non_superuser(
    use_shared_resource_setting,
    admin_client: APIClient,
    new_user: models.User,
):
    data = {"is_superuser": True}

    response = admin_client.patch(
        f"{api_url_v1}/users/{new_user.id}/", data=data
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    user_obj = models.User.objects.get(id=new_user.id)
    assert user_obj.is_superuser is False


@pytest.mark.django_db
def test_create_superuser(
    superuser_client: APIClient,
    user_api_client: APIClient,
    org_admin_rd,
    default_user,
):
    create_user_data = {
        "username": "test.user",
        "first_name": "Test",
        "last_name": "User",
        "email": "test.user@example.com",
        "password": "secret",
        "is_superuser": True,
    }

    response = superuser_client.post(
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
    org_admin_rd.give_permission(default_user, org)
    response = user_api_client.post(
        f"{api_url_v1}/users/", data=create_user_data
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_modify_superuser_as_superuser(superuser_client: APIClient):
    other_user = models.User.objects.create(username="other-user")
    assert other_user.is_superuser is False  # sanity
    url = reverse("user-detail", kwargs={"pk": other_user.pk})
    response = superuser_client.patch(url, data={"is_superuser": True})
    assert response.status_code == status.HTTP_200_OK
    assert response.data["is_superuser"] is True


@pytest.mark.django_db
def test_modify_superuser_as_org_admin(
    user_api_client: APIClient,
    org_admin_rd,
    org_member_rd,
    default_user,
):
    # Set up, giving admin access allows user to modify other_user
    other_user = models.User.objects.create(username="other-user")
    org = models.Organization.objects.first()
    # NOTE: default_user is the user for user_api_client
    org_admin_rd.give_permission(default_user, org)
    org_member_rd.give_permission(other_user, org)

    # Changing any ordinary field is fine
    url = reverse("user-detail", kwargs={"pk": other_user.pk})
    r = user_api_client.patch(url, data={"last_name": "Meyers"})
    assert r.status_code == status.HTTP_200_OK

    # Promoting other_user to superuser is not something user can do
    r = user_api_client.patch(url, data={"is_superuser": True})
    assert r.status_code == status.HTTP_403_FORBIDDEN

    # User should not be able to promote themself to superuser
    # but this serializer does not list is_superuser field
    # so response may be a 200 and that is still okay
    assert default_user.is_superuser is False  # sanity
    r = user_api_client.patch(
        f"{api_url_v1}/users/me/", data={"is_superuser": True}
    )
    default_user.refresh_from_db()
    assert default_user.is_superuser is False


@pytest.mark.django_db
def test_organization_admin_can_create_user(
    default_user, user_api_client, org_admin_rd
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
    org_admin_rd.give_permission(default_user, org)
    response = user_api_client.post(
        f"{api_url_v1}/users/", data=create_user_data
    )
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_retrieve_user_details(
    superuser_client: APIClient,
    user_api_client: APIClient,
    default_user: models.User,
):
    response = superuser_client.get(f"{api_url_v1}/users/{default_user.id}/")
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

    # user can see themselves and admins, but not unrelated users
    other_user = models.User.objects.create_user(username="another-user")
    response = user_api_client.get(f"{api_url_v1}/users/{other_user.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_retrieve_system_user(
    superuser_client: APIClient, system_user: models.User
):
    response = superuser_client.get(f"{api_url_v1}/users/{system_user.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == system_user.id


@pytest.mark.django_db
def test_list_users(
    admin_client: APIClient,
    admin_user: models.User,
    system_user: models.User,
):
    response = admin_client.get(f"{api_url_v1}/users/")
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
    assert results[0]["id"] != system_user.id


@pytest.mark.django_db
def test_list_users_filter_superuser(
    admin_client: APIClient,
    admin_user: models.User,
    super_user: models.User,
):
    response = admin_client.get(f"{api_url_v1}/users/")
    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]
    assert len(results) == 2

    # retrieve only superusers
    response = admin_client.get(f"{api_url_v1}/users/?is_superuser=true")
    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["id"] == super_user.id
    assert results[0]["is_superuser"] is True

    # retrieve only non-superusers
    response = admin_client.get(f"{api_url_v1}/users/?is_superuser=false")
    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["id"] == admin_user.id
    assert results[0]["is_superuser"] is False


@pytest.mark.django_db
def test_partial_update_user(
    admin_client: APIClient,
    admin_user: models.User,
):
    data = {"first_name": "Anakin"}
    response = admin_client.patch(
        f"{api_url_v1}/users/{admin_user.id}/", data=data
    )
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
def test_partial_update_user_forbidden(
    use_shared_resource_setting,
    admin_client: APIClient,
    admin_user: models.User,
):
    data = {"first_name": "Anakin"}
    response = admin_client.patch(
        f"{api_url_v1}/users/{admin_user.id}/", data=data
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_delete_user(
    superuser_client: APIClient,
    default_user: models.User,
):
    response = superuser_client.delete(
        f"{api_url_v1}/users/{default_user.id}/"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert models.User.objects.filter(id=default_user.id).count() == 0


@pytest.mark.django_db
def test_delete_user_forbidden(
    use_shared_resource_setting,
    superuser_client: APIClient,
    default_user: models.User,
):
    response = superuser_client.delete(
        f"{api_url_v1}/users/{default_user.id}/"
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_delete_user_not_allowed(
    admin_client: APIClient,
    admin_user: models.User,
):
    response = admin_client.delete(f"{api_url_v1}/users/{admin_user.id}/")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    assert models.User.objects.filter(id=admin_user.id).count() == 1


@pytest.mark.django_db
def test_list_users_filter_username(
    admin_client: APIClient,
    admin_user: models.User,
    default_user: models.User,
):
    response = admin_client.get(
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
    admin_client: APIClient,
    admin_user: models.User,
):
    response = admin_client.get(f"{api_url_v1}/users/?username=test")
    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]

    assert len(results) == 0


@pytest.mark.django_db
def test_list_users_filter_by_ansible_id(
    admin_client: APIClient,
    admin_user: models.User,
    default_user: models.User,
):
    filter = default_user.resource.ansible_id
    response = admin_client.get(
        f"{api_url_v1}/users/?resource__ansible_id={filter}"
    )
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

    fake_ansible_id = "918b16e3-82b9-4487-8e23-df0ff50afee8"
    response = admin_client.get(
        f"{api_url_v1}/users/?resource__ansible_id={fake_ansible_id}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 0


@pytest.mark.django_db
def test_resources_remain_after_user_delete(
    base_client: APIClient,
    admin_user: models.User,
    default_user: models.User,
    preseed_credential_types,
    default_organization,
    activation_payload: Dict[str, Any],
):
    # Give default user permission to create resources
    admin_role = RoleDefinition.objects.create(
        name="Elevated User",
        content_type=ContentType.objects.get_for_model(default_organization),
    )
    admin_role.permissions.add(*DABPermission.objects.all())
    admin_role.give_permission(default_user, default_organization)
    base_client.force_authenticate(user=default_user)

    # Create activation
    response = base_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    activation_id = response.data["id"]

    # Create event stream credential
    secret = secrets.token_hex(32)
    inputs = {
        "auth_type": "basic",
        "username": default_user.username,
        "password": secret,
        "http_header_key": "Authorization",
    }
    obj = create_event_stream_credential(
        base_client, enums.EventStreamCredentialType.BASIC.value, inputs
    )
    # Create event stream
    data_in = {
        "name": "test-es-1",
        "eda_credential_id": obj["id"],
        "event_stream_type": obj["credential_type"]["kind"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(base_client, data_in)

    # Delete user
    base_client.force_authenticate(user=admin_user)
    response = base_client.delete(f"{api_url_v1}/users/{default_user.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Ensure activation and event stream remain
    assert models.EventStream.objects.filter(id=event_stream.id).count() == 1
    assert models.Activation.objects.filter(id=activation_id).count() == 1

    # Ensure user is marked as deleted in event stream return
    response = base_client.get(
        f"{api_url_v1}/event-streams/{event_stream.id}/"
    )
    assert response.status_code == 200
    assert response.data["owner"] == ""


@pytest.mark.django_db
def test_list_users_filter_by_password(
    default_user: models.User, admin_client: APIClient
):
    response = admin_client.get(
        f"{api_url_v1}/users/?password__icontains={default_user.password}"
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert (
        "Filtering on field password is not allowed."
        in response.data["detail"]
    )
