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
from unittest import mock

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from aap_eda.core.utils.credentials import inputs_to_store
from tests.integration.constants import api_url_v1


# Test: List \ Retrieve project
# -------------------------------------
@pytest.mark.django_db
def test_list_projects(
    default_project: models.Project,
    new_project: models.Project,
    client: APIClient,
):
    projects = [default_project, new_project]
    response = client.get(f"{api_url_v1}/projects/")
    assert response.status_code == status.HTTP_200_OK
    for data, project in zip(response.json()["results"], projects):
        assert_project_base_data(data, project)
        assert_project_fk_data(data, project)


@pytest.mark.django_db
def test_list_projects_filter_name(
    default_project: models.Project,
    new_project: models.Project,
    client: APIClient,
):
    test_name = default_project.name
    response = client.get(f"{api_url_v1}/projects/?name={test_name}")
    data = response.json()["results"][0]
    assert response.status_code == status.HTTP_200_OK
    assert_project_base_data(data, default_project)
    assert_project_fk_data(data, default_project)


@pytest.mark.django_db
def test_list_projects_filter_name_none_exist(
    default_project: models.Project,
    client: APIClient,
):
    test_name = "test-not-exist"
    response = client.get(f"{api_url_v1}/projects/?name={test_name}")
    data = response.json()["results"]
    assert response.status_code == status.HTTP_200_OK
    assert data == []


@pytest.mark.django_db
def test_retrieve_project(
    default_project: models.Project,
    client: APIClient,
):
    response = client.get(f"{api_url_v1}/projects/{default_project.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert_project_base_data(response.json(), default_project)
    assert_project_related_data(response.json(), default_project)


@pytest.mark.django_db
def test_retrieve_project_failed_state(
    new_project: models.Project, client: APIClient
):
    response = client.get(f"{api_url_v1}/projects/{new_project.id}/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["import_state"] == "failed"
    assert data["import_error"] == "Unexpected error. Please contact support."

    assert_project_base_data(data, new_project)
    assert_project_related_data(data, new_project)


@pytest.mark.django_db
def test_retrieve_project_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/projects/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# Test: Create project
# -------------------------------------
@pytest.mark.django_db
@mock.patch("aap_eda.tasks.import_project")
def test_create_project(
    import_project_task: mock.Mock,
    client: APIClient,
):
    job_id = "3677eb4a-de4a-421a-a73b-411aa502484d"
    job = mock.Mock(id=job_id)
    import_project_task.delay.return_value = job

    cred_type = models.CredentialType.objects.create(
        name="type1", inputs={"fields": [{"id": "user", "type": "string"}]}
    )
    cred_inputs = inputs_to_store({"user": "me"})
    eda_credential = models.EdaCredential.objects.create(
        name="credential1", credential_type=cred_type, inputs=cred_inputs
    )
    sv_cred_inputs = inputs_to_store({"user": "him"})
    sv_credential = models.EdaCredential.objects.create(
        name="svcred1", credential_type=cred_type, inputs=sv_cred_inputs
    )

    bodies = [
        {
            "name": "test-project-01",
            "url": "https://git.example.com/acme/project-01",
            "eda_credential_id": eda_credential.id,
            "signature_validation_credential_id": sv_credential.id,
            "scm_branch": "main",
            "scm_refspec": "ref1",
        },
        {
            "name": "test-project-02",
            "url": "https://git.example.com/acme/project-02",
            "verify_ssl": False,
            "proxy": "myproxy.com",
        },
    ]

    for body in bodies:
        response = client.post(
            f"{api_url_v1}/projects/",
            data=body,
        )

        assert response.status_code == status.HTTP_201_CREATED

        data = response.json()

        try:
            project = models.Project.objects.get(pk=data["id"])
        except models.Project.DoesNotExist:
            raise AssertionError("Project doesn't exist in the database")

        # Check that project was created with valid data
        assert project.name == body["name"]
        assert project.url == body["url"]
        assert (
            project.verify_ssl is body["verify_ssl"]
            if "verify_ssl" in body
            else True
        )
        assert project.import_state == "pending"
        assert str(project.import_task_id) == job_id

        # Check that response returned the valid representation of the project
        assert_project_base_data(data, project)
        assert_project_fk_data(data, project)

        # Check that import task job was created
        import_project_task.delay.assert_called_with(project_id=project.id)


@pytest.mark.django_db
def test_create_project_name_conflict(
    default_project: models.Project, client: APIClient
):
    response = client.post(
        f"{api_url_v1}/projects/",
        data={
            "name": default_project.name,
            "url": "https://git.example.com/acme/project-01",
        },
    )
    # FIXME(cutwater): DRF serializers return HTTP 400 Bad Request
    #   for unique violations, instead of 409 Conflict.
    #   We need to handle this either at serializer level or global
    #   error handler level.
    #   See https://github.com/encode/django-rest-framework/issues/1848
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# Test: Sync project
# -------------------------------------
@pytest.mark.django_db
@mock.patch("aap_eda.tasks.sync_project")
@pytest.mark.parametrize(
    "initial_state",
    [
        models.Project.ImportState.COMPLETED,
        models.Project.ImportState.FAILED,
    ],
)
def test_sync_project(
    sync_project_task: mock.Mock,
    client: APIClient,
    initial_state: models.Project.ImportState,
    default_project: models.Project,
):
    default_project.import_state = initial_state
    default_project.save(update_fields=["import_state"])

    job_id = "3677eb4a-de4a-421a-a73b-411aa502484d"
    job = mock.Mock(id=job_id)
    sync_project_task.delay.return_value = job

    response = client.post(f"{api_url_v1}/projects/{default_project.id}/sync/")
    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()

    default_project.refresh_from_db()
    assert default_project.import_state == "pending"
    assert default_project.import_error is None
    assert str(default_project.import_task_id) == job_id

    assert_project_base_data(data, default_project)
    assert_project_fk_data(data, default_project)

    sync_project_task.delay.assert_called_once_with(
        project_id=default_project.id,
    )


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.sync_project")
@pytest.mark.parametrize(
    "initial_state",
    [
        models.Project.ImportState.PENDING,
        models.Project.ImportState.RUNNING,
    ],
)
def test_sync_project_conflict_already_running(
    sync_project_task: mock.Mock,
    client: APIClient,
    initial_state: models.Project.ImportState,
    default_project: models.Project,
):
    default_project.import_state = initial_state
    default_project.import_task_id = None
    default_project.save(update_fields=["import_state", "import_task_id"])

    response = client.post(f"{api_url_v1}/projects/{default_project.id}/sync/")
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "detail": "Project import or sync is already running."
    }

    sync_project_task.delay.assert_not_called()
    default_project.refresh_from_db()
    assert default_project.import_state == initial_state
    assert default_project.import_task_id is None


@pytest.mark.django_db
def test_sync_project_not_exist(client: APIClient):
    response = client.post(f"{api_url_v1}/projects/42/sync/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# Test: Partial update project
# -------------------------------------
@pytest.mark.django_db
def test_update_project_not_found(
    default_project: models.Project, client: APIClient
):
    response = client.get(f"{api_url_v1}/projects/{default_project.id}/")
    data = response.json()

    response = client.patch(f"{api_url_v1}/projects/42/", data=data)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_update_project_with_400(
    default_project: models.Project,
    new_project: models.Project,
    client: APIClient,
):
    response = client.get(f"{api_url_v1}/projects/{default_project.id}/")
    data = {
        "name": new_project.name,
        "git_hash": default_project.git_hash,
        "credential_id": default_project.credential_id,
    }
    # test empty string validator
    response = client.patch(
        f"{api_url_v1}/projects/{default_project.id}/", data={"name": ""}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["name"][0] == "This field may not be blank."
    # test unique name validator
    response = client.patch(
        f"{api_url_v1}/projects/{default_project.id}/", data=data
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["name"][0] == "Project with this name already exists."
    # test non-existent dependent object reference
    response = client.get(f"{api_url_v1}/projects/{default_project.id}/")
    data = {
        "name": "new project name",
        "eda_credential_id": 87,
    }
    response = client.patch(
        f"{api_url_v1}/projects/{default_project.id}/", data=data
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["errors"] == "EdaCredential [87] not found"


@pytest.mark.django_db
def test_partial_update_project(
    new_project: models.Project,
    default_eda_credential: models.EdaCredential,
    client: APIClient,
    check_permission_mock: mock.Mock,
):
    assert new_project.eda_credential_id is None
    assert new_project.signature_validation_credential_id is None
    assert new_project.verify_ssl is False

    new_data = {
        "name": "new-project-updated",
        "eda_credential_id": default_eda_credential.id,
        "signature_validation_credential_id": default_eda_credential.id,
        "scm_branch": "main",
        "scm_refspec": "ref1",
        "verify_ssl": True,
        "proxy": "myproxy.com",
    }
    response = client.patch(
        f"{api_url_v1}/projects/{new_project.id}/",
        data=new_data,
    )
    assert response.status_code == status.HTTP_200_OK

    new_project.refresh_from_db()
    assert new_project.name == new_data["name"]
    assert new_project.eda_credential.id == new_data["eda_credential_id"]
    assert (
        new_project.signature_validation_credential.id
        == new_data["eda_credential_id"]
    )
    assert new_project.verify_ssl is new_data["verify_ssl"]

    assert_project_base_data(response.json(), new_project)
    assert_project_fk_data(response.json(), new_project)


@pytest.mark.django_db
def test_delete_project(
    new_project: models.Project,
    client: APIClient,
):
    response = client.delete(f"{api_url_v1}/projects/{new_project.id}/")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not models.Project.objects.filter(pk=new_project.id).exists()


@pytest.mark.django_db
def test_delete_project_not_found(client: APIClient):
    response = client.delete(f"{api_url_v1}/projects/42/")

    assert response.status_code == status.HTTP_404_NOT_FOUND


# Utils
# -------------------------------------
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def assert_project_base_data(
    response: Dict[str, Any], expected: models.Project
):
    assert response["id"] == expected.id
    assert response["name"] == expected.name
    assert response["description"] == expected.description
    assert response["url"] == expected.url
    assert response["git_hash"] == expected.git_hash
    assert response["verify_ssl"] == expected.verify_ssl
    assert response["import_state"] == expected.import_state
    assert response["import_error"] == expected.import_error
    assert response["created_at"] == expected.created_at.strftime(
        DATETIME_FORMAT
    )
    assert response["modified_at"] == expected.modified_at.strftime(
        DATETIME_FORMAT
    )


def assert_project_fk_data(response: Dict[str, Any], expected: models.Project):
    if expected.eda_credential:
        assert response["eda_credential_id"] == expected.eda_credential.id
    else:
        assert not response["eda_credential_id"]
    if expected.signature_validation_credential:
        assert (
            response["signature_validation_credential_id"]
            == expected.signature_validation_credential.id
        )
    else:
        assert not response["signature_validation_credential_id"]
    if expected.organization:
        assert response["organization_id"] == expected.organization.id
    else:
        assert not response["organization_id"]


def assert_project_related_data(
    response: Dict[str, Any], expected: models.Project
):
    if expected.eda_credential:
        credential_data = response["eda_credential"]
        assert credential_data["id"] == expected.eda_credential.id
        assert credential_data["name"] == expected.eda_credential.name
        assert (
            credential_data["description"]
            == expected.eda_credential.description
        )
        assert credential_data["managed"] == expected.eda_credential.managed
        assert (
            credential_data["credential_type_id"]
            == expected.eda_credential.credential_type.id
        )
    else:
        assert not response["eda_credential"]
    if expected.organization:
        organization_data = response["organization"]
        assert organization_data["id"] == expected.organization.id
        assert organization_data["name"] == expected.organization.name
        assert (
            organization_data["description"]
            == expected.organization.description
        )
    else:
        assert not response["organization"]
