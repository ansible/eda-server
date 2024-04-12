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
import datetime
from typing import Any, Dict
from unittest import mock

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from aap_eda.core.enums import Action, ResourceType
from aap_eda.core.utils.credentials import inputs_to_display, inputs_to_store
from tests.integration.constants import api_url_v1


# Test: List \ Retrieve project
# -------------------------------------
@pytest.mark.django_db
def test_list_projects(client: APIClient, check_permission_mock: mock.Mock):
    cred_type = models.CredentialType.objects.create(
        name="credtype",
        inputs={},
    )
    projects = models.Project.objects.bulk_create(
        [
            models.Project(
                name="test-project-01",
                url="https://git.example.com/acme/project-01",
                git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
                eda_credential=models.EdaCredential.objects.create(
                    name="credential1",
                    credential_type=cred_type,
                    inputs="sec1",
                ),
                signature_validation_credential=models.EdaCredential.objects.create(  # noqa: E501
                    name="svcred1", credential_type=cred_type, inputs="sec2"
                ),
                scm_branch="main",
                import_state=models.Project.ImportState.PENDING,
                import_task_id="c8a7a0e3-05e7-4376-831a-6b8af80107bd",
            ),
            models.Project(
                name="test-project-02",
                url="https://git.example.com/acme/project-02",
                description="Project description.",
                git_hash="06a71890b48189edc0b7afccf18285ec042ce302",
                scm_refspec="refspec",
                verify_ssl=False,
                proxy="http://myproxy.com",
                import_state=models.Project.ImportState.COMPLETED,
                import_task_id="46e289a7-9dcc-4baa-a49a-a6ca756d9b71",
            ),
        ]
    )
    response = client.get(f"{api_url_v1}/projects/")
    assert response.status_code == status.HTTP_200_OK
    for data, project in zip(response.json()["results"], projects):
        project.refresh_from_db()
        assert_project_data(data, project)

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.PROJECT, Action.READ
    )


@pytest.mark.django_db
def test_list_projects_filter_name(client: APIClient):
    projects = models.Project.objects.bulk_create(
        [
            models.Project(
                name="test-project-01",
                url="https://git.example.com/acme/project-01",
                git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
            ),
            models.Project(
                name="test-project-02",
                url="https://git.example.com/acme/project-02",
                description="Project description.",
                git_hash="06a71890b48189edc0b7afccf18285ec042ce302",
            ),
        ]
    )
    test_name = "test-project-01"
    response = client.get(f"{api_url_v1}/projects/?name={test_name}")
    data = response.json()["results"][0]
    project = projects[0]
    assert response.status_code == status.HTTP_200_OK
    project.refresh_from_db()
    assert_project_data(data, project)


@pytest.mark.django_db
def test_list_projects_filter_name_none_exist(client: APIClient):
    models.Project.objects.bulk_create(
        [
            models.Project(
                name="test-project-01",
                url="https://git.example.com/acme/project-01",
                git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
            ),
            models.Project(
                name="test-project-02",
                url="https://git.example.com/acme/project-02",
                description="Project description.",
                git_hash="06a71890b48189edc0b7afccf18285ec042ce302",
            ),
        ]
    )
    test_name = "test-doesnt-exist"
    response = client.get(f"{api_url_v1}/projects/?name={test_name}")
    data = response.json()["results"]
    assert response.status_code == status.HTTP_200_OK
    assert data == []


@pytest.mark.django_db
def test_retrieve_project(client: APIClient, check_permission_mock: mock.Mock):
    cred_type = models.CredentialType.objects.create(
        name="type1", inputs={"fields": [{"id": "user", "type": "string"}]}
    )
    cred_inputs = inputs_to_store({"user": "me"})
    sv_cred_inputs = inputs_to_store({"user": "him"})
    project = models.Project.objects.create(
        name="test-project-01",
        eda_credential=models.EdaCredential.objects.create(
            name="credential1", credential_type=cred_type, inputs=cred_inputs
        ),
        signature_validation_credential=models.EdaCredential.objects.create(
            name="svcred1", credential_type=cred_type, inputs=sv_cred_inputs
        ),
        scm_branch="main",
        scm_refspec="ref1",
        proxy="http://user:secret@myproxy.com",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
    )
    project.refresh_from_db()
    response = client.get(f"{api_url_v1}/projects/{project.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert_project_data(response.json(), project)

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.PROJECT, Action.READ
    )


@pytest.mark.django_db
def test_retrieve_project_failed_state(client: APIClient):
    project = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
        import_state=models.Project.ImportState.FAILED,
        import_task_id="3677eb4a-de4a-421a-a73b-411aa502484d",
        import_error="Unexpected error. Please contact support.",
    )
    project.refresh_from_db()
    response = client.get(f"{api_url_v1}/projects/{project.id}/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["import_state"] == "failed"
    assert data["import_error"] == "Unexpected error. Please contact support."

    assert_project_data(data, project)


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
    check_permission_mock: mock.Mock,
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
        assert_project_data(data, project)

        # Check that import task job was created
        import_project_task.delay.assert_called_with(project_id=project.id)

        check_permission_mock.assert_called_with(
            mock.ANY, mock.ANY, ResourceType.PROJECT, Action.CREATE
        )


@pytest.mark.django_db
def test_create_project_name_conflict(client: APIClient):
    models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
    )
    response = client.post(
        f"{api_url_v1}/projects/",
        data={
            "name": "test-project-01",
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
    check_permission_mock: mock.Mock,
    initial_state: models.Project.ImportState,
):
    project = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
        import_state=initial_state,
    )

    job_id = "3677eb4a-de4a-421a-a73b-411aa502484d"
    job = mock.Mock(id=job_id)
    sync_project_task.delay.return_value = job

    response = client.post(f"{api_url_v1}/projects/{project.id}/sync/")
    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()

    try:
        project = models.Project.objects.get(pk=data["id"])
    except models.Project.DoesNotExist:
        raise AssertionError("Project doesn't exist in the database")

    assert project.import_state == "pending"
    assert project.import_error is None
    assert str(project.import_task_id) == job_id

    assert_project_data(data, project)

    sync_project_task.delay.assert_called_once_with(
        project_id=project.id,
    )
    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.PROJECT, Action.UPDATE
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
    check_permission_mock: mock.Mock,
    initial_state: models.Project.ImportState,
):
    project = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
        import_state=initial_state,
    )

    response = client.post(f"{api_url_v1}/projects/{project.id}/sync/")
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "detail": "Project import or sync is already running."
    }

    project.refresh_from_db()
    assert project.import_state == initial_state
    assert project.import_task_id is None

    sync_project_task.delay.assert_not_called()

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.PROJECT, Action.UPDATE
    )


@pytest.mark.django_db
def test_sync_project_not_exist(client: APIClient):
    response = client.post(f"{api_url_v1}/projects/42/sync/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# Test: Partial update project
# -------------------------------------
@pytest.mark.django_db
def test_update_project_not_found(client: APIClient):
    project = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
    )
    response = client.get(f"{api_url_v1}/projects/{project.id}/")
    data = response.json()

    response = client.patch(f"{api_url_v1}/projects/42/", data=data)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_update_project_with_400(client: APIClient):
    first = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
    )
    second = models.Project.objects.create(
        name="test-project-02",
        url="https://git.example.com/acme/project-02",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
    )
    response = client.get(f"{api_url_v1}/projects/{first.id}/")
    data = {
        "name": second.name,
        "git_hash": first.git_hash,
        "credential_id": first.credential_id,
    }
    # test empty string validator
    response = client.patch(
        f"{api_url_v1}/projects/{first.id}/", data={"name": ""}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["name"][0] == "This field may not be blank."
    # test unique name validator
    response = client.patch(f"{api_url_v1}/projects/{first.id}/", data=data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["name"][0] == "Project with this name already exists."
    # test non-existent dependent object reference
    response = client.get(f"{api_url_v1}/projects/{first.id}/")
    data = {
        "name": "new project name",
        "eda_credential_id": 2,
    }
    response = client.patch(f"{api_url_v1}/projects/{first.id}/", data=data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["errors"] == "EdaCredential [2] not found"


@pytest.mark.django_db
def test_partial_update_project(
    client: APIClient, check_permission_mock: mock.Mock
):
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

    project = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
        proxy="http://user:secret@myproxy.com",
    )
    assert project.eda_credential_id is None
    assert project.signature_validation_credential_id is None
    assert project.verify_ssl is True

    data = {
        "name": "test-project-01-updated",
        "eda_credential_id": eda_credential.id,
        "signature_validation_credential_id": sv_credential.id,
        "scm_branch": "main",
        "scm_refspec": "ref1",
        "verify_ssl": False,
        "proxy": "http://user:$encrypted$@myproxy.com",
    }
    response = client.patch(
        f"{api_url_v1}/projects/{project.id}/",
        data,
    )
    assert response.status_code == status.HTTP_200_OK

    project = models.Project.objects.get(pk=project.id)
    assert_project_data(data, project)

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.PROJECT, Action.UPDATE
    )


@pytest.mark.django_db
def test_partial_update_project_bad_proxy(
    client: APIClient, check_permission_mock: mock.Mock
):
    project = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
        proxy="http://user:secret@myproxy.com",
    )

    data = {
        "name": "test-project-01-updated",
        "proxy": "http://new-user:$encrypted$@myproxy.com",
    }
    response = client.patch(
        f"{api_url_v1}/projects/{project.id}/",
        data,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["errors"]
        == "The password in the proxy field should be unencrypted"
    )


@pytest.mark.django_db
def test_delete_project(client: APIClient, check_permission_mock: mock.Mock):
    project = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
    )
    response = client.delete(f"{api_url_v1}/projects/{project.id}/")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not models.Project.objects.filter(pk=project.id).exists()

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.PROJECT, Action.DELETE
    )


@pytest.mark.django_db
def test_delete_project_not_found(client: APIClient):
    response = client.delete(f"{api_url_v1}/projects/42/")

    assert response.status_code == status.HTTP_404_NOT_FOUND


# Utils
# -------------------------------------
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def assert_project_data(data: Dict[str, Any], project: models.Project):
    for key, value in data.items():
        project_value = getattr(project, key, None)
        if isinstance(project_value, datetime.datetime):
            project_value = project_value.strftime(DATETIME_FORMAT)

        if isinstance(project_value, models.EdaCredential):
            assert value == get_credential_details(project_value)
        else:
            if key == "proxy":
                project_value = project_value.get_secret_value().replace(
                    "secret", "$encrypted$"
                )
            assert value == project_value


def get_credential_details(credential: models.EdaCredential) -> dict:
    credential.refresh_from_db()
    return {
        "id": credential.id,
        "name": credential.name,
        "description": credential.description,
        "credential_type_id": credential.credential_type.id,
        "managed": credential.managed,
        "inputs": inputs_to_display(
            credential.credential_type.inputs,
            credential.inputs.get_secret_value(),
        ),
    }
