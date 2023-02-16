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
from tests.integration.constants import api_url_v1


# Test: List \ Retrieve project
# -------------------------------------
@pytest.mark.django_db
def test_list_projects(client: APIClient):
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
    response = client.get(f"{api_url_v1}/projects/")
    assert response.status_code == status.HTTP_200_OK
    for data, project in zip(response.data["results"], projects):
        assert_project_data(data, project)


@pytest.mark.django_db
def test_retrieve_project(client: APIClient):
    project = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
    )
    response = client.get(f"{api_url_v1}/projects/{project.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert_project_data(response.json(), project)


@pytest.mark.django_db
def test_retrieve_project_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/projects/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# Test: Create project
# -------------------------------------
@pytest.mark.django_db
@mock.patch("aap_eda.tasks.import_project")
def test_create_project(import_project_task: mock.Mock, client: APIClient):
    job_id = "3677eb4a-de4a-421a-a73b-411aa502484d"
    job = mock.Mock(id=job_id)
    import_project_task.delay.return_value = job

    response = client.post(
        f"{api_url_v1}/projects/",
        data={
            "name": "test-project-01",
            "url": "https://git.example.com/acme/project-01",
        },
    )
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == {
        "id": job_id,
        "href": f"http://testserver{api_url_v1}/tasks/{job_id}/",
    }

    import_project_task.delay.assert_called_once_with(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
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
def test_sync_project(sync_project_task: mock.Mock, client: APIClient):
    project = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
    )

    job_id = "3677eb4a-de4a-421a-a73b-411aa502484d"
    job = mock.Mock(id=job_id)
    sync_project_task.delay.return_value = job

    response = client.post(f"{api_url_v1}/projects/{project.id}/sync/")
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == {
        "id": job_id,
        "href": f"http://testserver{api_url_v1}/tasks/{job_id}/",
    }

    sync_project_task.delay.assert_called_once_with(
        project_id=project.id,
    )


@pytest.mark.django_db
def test_sync_project_not_exist(client: APIClient):
    response = client.post(f"{api_url_v1}/projects/42/sync/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# Test: Update project
# -------------------------------------
@pytest.mark.django_db
def test_update_project(client: APIClient):
    project = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
    )
    response = client.get(f"{api_url_v1}/projects/{project.id}/")
    assert response.status_code == status.HTTP_200_OK

    update_data = {
        **response.json(),
        "name": "test-project-01-updated",
        "description": "Updated description",
    }

    response = client.put(
        f"{api_url_v1}/projects/{project.id}/", data=update_data
    )
    assert response.status_code == status.HTTP_200_OK

    project = models.Project.objects.get(pk=project.id)
    assert project.name == "test-project-01-updated"
    assert project.description == "Updated description"

    assert_project_data(response.json(), project)


@pytest.mark.django_db
def test_update_project_not_found(client: APIClient):
    project = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
    )
    response = client.get(f"{api_url_v1}/projects/{project.id}/")
    data = response.json()

    response = client.get(f"{api_url_v1}/projects/42/", data=data)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_update_project_conflict(client: APIClient):
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
        **response.json(),
        "name": second.name,
    }
    response = client.put(f"{api_url_v1}/projects/{first.id}/", data=data)
    # NOTE(cutwater): Should be 409 Conflict
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "name": ["project with this name already exists."]
    }


@pytest.mark.django_db
def test_update_project_empty_name(client: APIClient):
    project = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
    )
    response = client.get(f"{api_url_v1}/projects/{project.id}/")
    data = {
        **response.json(),
        "name": "",
    }
    response = client.put(f"{api_url_v1}/projects/{project.id}/", data=data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"name": ["This field may not be blank."]}


# Test: Partial update project
# -------------------------------------


@pytest.mark.django_db
def test_partial_update_project(client: APIClient):
    project = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
    )
    response = client.put(
        f"{api_url_v1}/projects/{project.id}/",
        data={"name": "test-project-01-updated"},
    )
    assert response.status_code == status.HTTP_200_OK

    project = models.Project.objects.get(pk=project.id)
    assert project.name == "test-project-01-updated"

    assert_project_data(response.json(), project)


# Test: Delete project
# -------------------------------------
# NOTE(cutwater): Remove this test and xfail marks below once
#  the project deletion is enabled
@pytest.mark.django_db
def test_delete_project_not_implemented(client: APIClient):
    project = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
    )
    response = client.delete(f"{api_url_v1}/projects/{project.id}/")

    assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED


@pytest.mark.xfail(
    reason=(
        "Project deletion is not allowed until"
        " resource versioning is implemented"
    ),
    strict=True,
)
@pytest.mark.django_db
def test_delete_project(client: APIClient):
    project = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
    )
    response = client.delete(f"{api_url_v1}/projects/{project.id}")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not models.Project.objects.filter(pk=project.id).exists()


@pytest.mark.xfail(
    reason=(
        "Project deletion is not allowed until"
        " resource versioning is implemented"
    ),
    strict=True,
)
@pytest.mark.django_db
def test_delete_project_not_found(client: APIClient):
    response = client.delete(f"{api_url_v1}/projects/42")

    assert response.status_code == status.HTTP_404_NOT_FOUND


# Utils
# -------------------------------------
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def assert_project_data(data: Dict[str, Any], project: models.Project):
    assert data == {
        "id": project.id,
        "url": project.url,
        "name": project.name,
        "description": project.description,
        "git_hash": project.git_hash,
        "created_at": project.created_at.strftime(DATETIME_FORMAT),
        "modified_at": project.modified_at.strftime(DATETIME_FORMAT),
    }
