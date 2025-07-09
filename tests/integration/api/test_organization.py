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

from typing import Any, Dict

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_list_organizations(
    default_organization: models.Organization, admin_client: APIClient
):
    response = admin_client.get(f"{api_url_v1}/organizations/")
    assert response.status_code == status.HTTP_200_OK
    result = response.data["results"][0]
    assert_organization_data(result, default_organization)


@pytest.mark.django_db
def test_list_organizations_filter_by_name(
    default_organization: models.Organization,
    new_organization: models.Organization,
    superuser_client: APIClient,  # only superuser can view both orgs
):
    filter = default_organization.name
    response = superuser_client.get(
        f"{api_url_v1}/organizations/?name={filter}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    result = response.data["results"][0]
    assert_organization_data(result, default_organization)

    response = superuser_client.get(
        f"{api_url_v1}/organizations/?name=non-existent-org"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 0


@pytest.mark.django_db
def test_list_organizations_filter_by_description(
    default_organization: models.Organization,
    new_organization: models.Organization,
    superuser_client: APIClient,  # only superuser can view both orgs
):
    filter = default_organization.description
    response = superuser_client.get(
        f"{api_url_v1}/organizations/?description={filter}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    result = response.data["results"][0]
    assert_organization_data(result, default_organization)

    response = superuser_client.get(
        f"{api_url_v1}/organizations/?description=non-existent-org"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 0


@pytest.mark.django_db
def test_list_organizations_filter_by_ansible_id(
    default_organization: models.Organization,
    new_organization: models.Organization,
    superuser_client: APIClient,  # only superuser can view both orgs
):
    filter = new_organization.resource.ansible_id
    response = superuser_client.get(
        f"{api_url_v1}/organizations/?resource__ansible_id={filter}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    result = response.data["results"][0]
    assert_organization_data(result, new_organization)

    fake_ansible_id = "918b16e3-82b9-4487-8e23-df0ff50afee8"
    response = superuser_client.get(
        f"{api_url_v1}/organizations/?resource__ansible_id={fake_ansible_id}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 0


@pytest.mark.django_db
def test_create_organization(
    use_local_resource_setting,
    base_client: APIClient,
    super_user: models.User,
):
    base_client.force_authenticate(user=super_user)
    data_in = {
        "name": "test-organization",
        "description": "Test Organization",
    }
    response = base_client.post(f"{api_url_v1}/organizations/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    org_id = response.data["id"]
    result = response.data
    assert result["name"] == data_in["name"]
    assert result["description"] == data_in["description"]
    assert models.Organization.objects.filter(pk=org_id).exists()


@pytest.mark.django_db
def test_create_organization_forbidden(
    use_shared_resource_setting,
    base_client: APIClient,
    super_user: models.User,
):
    base_client.force_authenticate(user=super_user)
    data_in = {
        "name": "test-organization",
        "description": "Test Organization",
    }
    response = base_client.post(f"{api_url_v1}/organizations/", data=data_in)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_retrieve_organization(
    default_organization: models.Organization, admin_client: APIClient
):
    response = admin_client.get(
        f"{api_url_v1}/organizations/{default_organization.id}/"
    )
    assert response.status_code == status.HTTP_200_OK

    assert_organization_data(response.data, default_organization)


@pytest.mark.django_db
def test_retrieve_organization_not_exist(admin_client: APIClient):
    response = admin_client.get(f"{api_url_v1}/organizations/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_partial_update_organization_success(
    use_local_resource_setting,
    new_organization: models.Organization,
    superuser_client: APIClient,
):
    new_data = {"name": "new-name", "description": "New Description"}
    response = superuser_client.patch(
        f"{api_url_v1}/organizations/{new_organization.id}/", data=new_data
    )
    assert response.status_code == status.HTTP_200_OK

    new_organization.refresh_from_db()
    assert_organization_data(response.data, new_organization)


@pytest.mark.django_db
def test_partial_update_organization_forbidden(
    use_shared_resource_setting,
    new_organization: models.Organization,
    superuser_client: APIClient,
):
    new_data = {"name": "new-name", "description": "New Description"}
    response = superuser_client.patch(
        f"{api_url_v1}/organizations/{new_organization.id}/", data=new_data
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_partial_update_default_organization_exception(
    use_local_resource_setting,
    default_organization: models.Organization,
    superuser_client: APIClient,
):
    new_data = {"name": "new-name", "description": "New Description"}
    response = superuser_client.patch(
        f"{api_url_v1}/organizations/{default_organization.id}/", data=new_data
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        response.data["detail"]
        == "The default organization cannot be modified."
    )
    assert models.Organization.objects.get(id=default_organization.id)


@pytest.mark.django_db
def test_delete_organization_success(
    use_local_resource_setting,
    new_organization: models.Organization,
    superuser_client: APIClient,
):
    response = superuser_client.delete(
        f"{api_url_v1}/organizations/{new_organization.id}/"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert (
        models.Organization.objects.filter(pk=int(new_organization.id)).count()
        == 0
    )


@pytest.mark.django_db
def test_delete_organization_conflict(
    use_local_resource_setting,
    default_organization: models.Organization,
    admin_client: APIClient,
):
    response = admin_client.delete(
        f"{api_url_v1}/organizations/{default_organization.id}/"
    )
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_delete_organization_forbidden(
    use_shared_resource_setting,
    new_organization: models.Organization,
    superuser_client: APIClient,
):
    response = superuser_client.delete(
        f"{api_url_v1}/organizations/{new_organization.id}/"
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_delete_organization_not_exist(
    use_local_resource_setting, admin_client: APIClient
):
    response = admin_client.delete(f"{api_url_v1}/organizations/100/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def assert_organization_data(
    response: Dict[str, Any], expected: models.Organization
):
    assert response["id"] == expected.id
    assert response["name"] == expected.name
    assert response["description"] == expected.description
    assert response["resource"] == {
        "ansible_id": expected.resource.ansible_id,
        "resource_type": expected.resource.resource_type,
    }
    assert response["created"] == expected.created.strftime(DATETIME_FORMAT)
    if expected.created_by:
        assert response["created_by"] == expected.created_by.id
    else:
        assert response["created_by"] == expected.created_by
    assert response["modified"] == expected.modified.strftime(DATETIME_FORMAT)
    if expected.modified_by:
        assert response["modified_by"] == expected.modified_by.id
    else:
        assert response["modified_by"] == expected.modified_by
