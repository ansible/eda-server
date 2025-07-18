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
def test_list_teams(default_team: models.Team, admin_client: APIClient):
    response = admin_client.get(f"{api_url_v1}/teams/")
    assert response.status_code == status.HTTP_200_OK
    result = response.data["results"][0]
    assert_team_data(result, default_team)


@pytest.mark.django_db
def test_list_teams_filter_by_name(
    default_team: models.Organization,
    new_team: models.Organization,
    admin_client: APIClient,
):
    filter = default_team.name
    response = admin_client.get(f"{api_url_v1}/teams/?name={filter}")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    result = response.data["results"][0]
    assert_team_data(result, default_team)

    response = admin_client.get(f"{api_url_v1}/teams/?name=non-existent-org")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 0


@pytest.mark.django_db
def test_list_teams_filter_by_description(
    default_team: models.Team, new_team: models.Team, admin_client: APIClient
):
    filter = default_team.description
    response = admin_client.get(f"{api_url_v1}/teams/?description={filter}")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    result = response.data["results"][0]
    assert_team_data(result, default_team)

    response = admin_client.get(
        f"{api_url_v1}/teams/?description=non-existent-org"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 0


@pytest.mark.django_db
def test_list_teams_filter_by_ansible_id(
    default_team: models.Team, new_team: models.Team, admin_client: APIClient
):
    filter = new_team.resource.ansible_id
    response = admin_client.get(
        f"{api_url_v1}/teams/?resource__ansible_id={filter}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    result = response.data["results"][0]
    assert_team_data(result, new_team)

    response = admin_client.get(
        f"{api_url_v1}/teams/?resource__ansible_id=non-existent-org"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 0


@pytest.mark.django_db
def test_create_team(
    use_local_resource_setting,
    default_organization: models.Organization,
    admin_client: APIClient,
):
    data_in = {
        "name": "test-team",
        "description": "Test Team",
        "organization_id": default_organization.id,
    }
    response = admin_client.post(f"{api_url_v1}/teams/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    team_id = response.data["id"]
    result = response.data
    assert result["name"] == data_in["name"]
    assert result["description"] == data_in["description"]
    assert result["organization_id"] == default_organization.id
    assert models.Team.objects.filter(pk=team_id).exists()


@pytest.mark.django_db
def test_create_team_forbidden(
    use_shared_resource_setting,
    default_organization: models.Organization,
    admin_client: APIClient,
):
    data_in = {
        "name": "test-team",
        "description": "Test Team",
        "organization_id": default_organization.id,
    }
    response = admin_client.post(f"{api_url_v1}/teams/", data=data_in)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_create_team_unique_name_constraint(
    default_organization: models.Organization,
    default_team: models.Team,
    admin_client: APIClient,
):
    data_in = {
        "name": default_team.name,
        "description": "Test Team",
        "organization_id": default_organization.id,
    }
    response = admin_client.post(f"{api_url_v1}/teams/", data=data_in)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()["non_field_errors"]
    assert "Team with this name already exists in the organization." in errors


@pytest.mark.django_db
def test_retrieve_team(default_team: models.Team, admin_client: APIClient):
    response = admin_client.get(f"{api_url_v1}/teams/{default_team.id}/")
    assert response.status_code == status.HTTP_200_OK

    assert_team_data(response.data, default_team)


@pytest.mark.django_db
def test_retrieve_team_not_exist(admin_client: APIClient):
    response = admin_client.get(f"{api_url_v1}/teams/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_partial_update_team(
    use_local_resource_setting,
    default_team: models.Team,
    admin_client: APIClient,
):
    new_data = {"name": "new-name", "description": "New Description"}
    response = admin_client.patch(
        f"{api_url_v1}/teams/{default_team.id}/", data=new_data
    )
    assert response.status_code == status.HTTP_200_OK

    default_team.refresh_from_db()
    assert_team_data(response.data, default_team)


@pytest.mark.django_db
def test_partial_update_team_forbidden(
    use_shared_resource_setting,
    default_team: models.Team,
    admin_client: APIClient,
):
    new_data = {"name": "new-name", "description": "New Description"}
    response = admin_client.patch(
        f"{api_url_v1}/teams/{default_team.id}/", data=new_data
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_delete_team_success(
    use_local_resource_setting,
    default_team: models.Team,
    admin_client: APIClient,
):
    response = admin_client.delete(f"{api_url_v1}/teams/{default_team.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert models.Team.objects.filter(pk=int(default_team.id)).count() == 0


@pytest.mark.django_db
def test_delete_team_forbidden(
    use_shared_resource_setting,
    default_team: models.Team,
    admin_client: APIClient,
):
    response = admin_client.delete(f"{api_url_v1}/teams/{default_team.id}/")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_delete_team_not_exist(
    use_local_resource_setting, admin_client: APIClient
):
    response = admin_client.delete(f"{api_url_v1}/teams/100/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def assert_team_data(response: Dict[str, Any], expected: models.Team):
    assert response["id"] == expected.id
    assert response["name"] == expected.name
    assert response["description"] == expected.description
    if "organization_id" in response:
        assert response["organization_id"] == expected.organization.id
    elif "organization" in response:
        assert response["organization"] == {
            "id": expected.organization.id,
            "name": expected.organization.name,
            "description": expected.organization.description,
        }
    else:
        AssertionError()  # fail if team has no organization
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
