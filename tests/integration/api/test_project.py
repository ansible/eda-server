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
import redis
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.api import exceptions as api_exc
from aap_eda.api.serializers.user import BasicUserSerializer
from aap_eda.core import enums, models
from aap_eda.core.utils.credentials import inputs_to_display, inputs_to_store
from tests.integration.constants import api_url_v1


# Test: List \ Retrieve project
# -------------------------------------
@pytest.mark.django_db
def test_list_projects(
    default_project: models.Project,
    new_project: models.Project,
    admin_client: APIClient,
):
    projects = [default_project, new_project]
    response = admin_client.get(f"{api_url_v1}/projects/")
    assert response.status_code == status.HTTP_200_OK
    for data, project in zip(response.json()["results"], projects):
        project.refresh_from_db()
        assert_project_data(data, project)


@pytest.mark.django_db
def test_list_projects_filter_name(
    default_project: models.Project,
    new_project: models.Project,
    admin_client: APIClient,
):
    test_name = default_project.name
    response = admin_client.get(f"{api_url_v1}/projects/?name={test_name}")
    data = response.json()["results"][0]
    assert response.status_code == status.HTTP_200_OK
    default_project.refresh_from_db()
    assert_project_data(data, default_project)


@pytest.mark.django_db
def test_list_projects_filter_name_none_exist(
    default_project: models.Project,
    admin_client: APIClient,
):
    test_name = "test-not-exist"
    response = admin_client.get(f"{api_url_v1}/projects/?name={test_name}")
    data = response.json()["results"]
    assert response.status_code == status.HTTP_200_OK
    assert data == []


@pytest.mark.django_db
def test_retrieve_project(
    default_project: models.Project,
    admin_client: APIClient,
):
    default_project.refresh_from_db()
    response = admin_client.get(f"{api_url_v1}/projects/{default_project.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert_project_data(response.json(), default_project)


@pytest.mark.django_db
def test_retrieve_project_failed_state(
    new_project: models.Project, admin_client: APIClient
):
    new_project.refresh_from_db()
    response = admin_client.get(f"{api_url_v1}/projects/{new_project.id}/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["import_state"] == "failed"
    assert data["import_error"] == "Unexpected error. Please contact support."

    assert_project_data(data, new_project)


@pytest.mark.django_db
def test_retrieve_project_not_exist(admin_client: APIClient):
    response = admin_client.get(f"{api_url_v1}/projects/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# Test: Create project
# -------------------------------------
@pytest.mark.parametrize(
    ("action", "credential_type", "status_code"),
    [
        (
            "create",
            enums.DefaultCredentialType.VAULT,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "create",
            enums.DefaultCredentialType.AAP,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "create",
            enums.DefaultCredentialType.GPG,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "create",
            enums.DefaultCredentialType.REGISTRY,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "create",
            enums.DefaultCredentialType.SOURCE_CONTROL,
            status.HTTP_201_CREATED,
        ),
        (
            "update",
            enums.DefaultCredentialType.VAULT,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "update",
            enums.DefaultCredentialType.AAP,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "update",
            enums.DefaultCredentialType.GPG,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "update",
            enums.DefaultCredentialType.REGISTRY,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "update",
            enums.DefaultCredentialType.SOURCE_CONTROL,
            status.HTTP_200_OK,
        ),
    ],
)
@pytest.mark.django_db
@mock.patch("aap_eda.tasks.import_project")
@mock.patch(
    "aap_eda.api.views.project.RedisDependencyMixin.redis_is_available"
)
def test_create_or_update_project_with_right_signature_credential(
    redis_available: mock.Mock,
    import_project_task: mock.Mock,
    admin_client: APIClient,
    new_project: models.Project,
    preseed_credential_types,
    default_gpg_credential,
    default_organization: models.Organization,
    action,
    credential_type,
    status_code,
):
    job_id = "3677eb4a-de4a-421a-a73b-411aa502484d"
    import_project_task.return_value = job_id
    credential = create_custom_credential(
        credential_type=credential_type, organization=default_organization
    )

    if action == "create":
        body = {
            "name": "test-project-01",
            "url": "https://git.example.com/acme/project-01",
            "eda_credential_id": credential.id,
            "signature_validation_credential_id": default_gpg_credential.id,
            "scm_branch": "main",
            "scm_refspec": "path/to/ref1",
            "organization_id": default_organization.id,
        }

        response = admin_client.post(
            f"{api_url_v1}/projects/",
            data=body,
        )
    else:
        assert new_project.eda_credential_id is None
        assert new_project.signature_validation_credential_id is None
        assert new_project.verify_ssl is False
        new_data = {
            "name": "new-project-updated",
            "eda_credential_id": credential.id,
            "signature_validation_credential_id": default_gpg_credential.id,
            "scm_branch": "main",
            "scm_refspec": "path/to/ref1",
            "verify_ssl": True,
            "proxy": "http://user:$encrypted$@myproxy.com",
        }
        response = admin_client.patch(
            f"{api_url_v1}/projects/{new_project.id}/",
            data=new_data,
        )

    assert response.status_code == status_code
    if status_code == status.HTTP_200_OK:
        new_project.refresh_from_db()
        assert new_project.name == new_data["name"]
        assert new_project.eda_credential.id == new_data["eda_credential_id"]
        assert (
            new_project.signature_validation_credential.id
            == new_data["signature_validation_credential_id"]
        )
        assert new_project.verify_ssl is new_data["verify_ssl"]

        assert_project_data(response.json(), new_project)
    elif status_code == status.HTTP_201_CREATED:
        project = models.Project.objects.get(id=response.data["id"])

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
        assert_project_data(response.data, project)

        # Check that import task job was created
        import_project_task.assert_called_with(project.id)
    else:
        assert (
            "The type of credential can only be one of ['Source Control']"
            in response.data["eda_credential_id"]
        )


@pytest.mark.parametrize(
    ("action", "credential_type", "status_code"),
    [
        (
            "create",
            enums.DefaultCredentialType.VAULT,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "create",
            enums.DefaultCredentialType.AAP,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "create",
            enums.DefaultCredentialType.GPG,
            status.HTTP_201_CREATED,
        ),
        (
            "create",
            enums.DefaultCredentialType.REGISTRY,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "create",
            enums.DefaultCredentialType.SOURCE_CONTROL,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "update",
            enums.DefaultCredentialType.VAULT,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "update",
            enums.DefaultCredentialType.AAP,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "update",
            enums.DefaultCredentialType.GPG,
            status.HTTP_200_OK,
        ),
        (
            "update",
            enums.DefaultCredentialType.REGISTRY,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "update",
            enums.DefaultCredentialType.SOURCE_CONTROL,
            status.HTTP_400_BAD_REQUEST,
        ),
    ],
)
@pytest.mark.django_db
@mock.patch("aap_eda.tasks.import_project")
@mock.patch(
    "aap_eda.api.views.project.RedisDependencyMixin.redis_is_available"
)
def test_create_or_update_project_with_right_eda_credential(
    redis_available: mock.Mock,
    import_project_task: mock.Mock,
    admin_client: APIClient,
    new_project: models.Project,
    preseed_credential_types,
    default_scm_credential,
    default_organization: models.Organization,
    admin_user: models.User,
    action,
    credential_type,
    status_code,
):
    job_id = "3677eb4a-de4a-421a-a73b-411aa502484d"
    import_project_task.return_value = job_id
    credential = create_custom_credential(
        credential_type=credential_type, organization=default_organization
    )

    if action == "create":
        body = {
            "name": "test-project-01",
            "url": "https://git.example.com/acme/project-01",
            "eda_credential_id": default_scm_credential.id,
            "signature_validation_credential_id": credential.id,
            "scm_branch": "main",
            "scm_refspec": "path/to/ref1",
            "organization_id": default_organization.id,
        }

        response = admin_client.post(
            f"{api_url_v1}/projects/",
            data=body,
        )
    else:
        assert new_project.eda_credential_id is None
        assert new_project.signature_validation_credential_id is None
        assert new_project.verify_ssl is False
        new_data = {
            "name": "new-project-updated",
            "eda_credential_id": default_scm_credential.id,
            "signature_validation_credential_id": credential.id,
            "scm_branch": "main",
            "scm_refspec": "path/to/ref1",
            "verify_ssl": True,
            "proxy": "http://user:$encrypted$@myproxy.com",
        }
        response = admin_client.patch(
            f"{api_url_v1}/projects/{new_project.id}/",
            data=new_data,
        )

    assert response.status_code == status_code
    if status_code == status.HTTP_200_OK:
        new_project.refresh_from_db()
        assert new_project.name == new_data["name"]
        assert new_project.eda_credential.id == new_data["eda_credential_id"]
        assert (
            new_project.signature_validation_credential.id
            == new_data["signature_validation_credential_id"]
        )
        assert new_project.verify_ssl is new_data["verify_ssl"]

        assert_project_data(response.json(), new_project)
    elif status_code == status.HTTP_201_CREATED:
        project = models.Project.objects.get(id=response.data["id"])

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

        assert project.created_by == admin_user
        assert project.modified_by == admin_user
        # Check that response returned the valid representation of the project
        assert_project_data(response.data, project)

        # Check that import task job was created
        import_project_task.assert_called_with(project.id)
    else:
        assert (
            "The type of credential can only be one of ['GPG Public Key']"
            in response.data["signature_validation_credential_id"]
        )


@pytest.mark.django_db
def test_create_project_with_none_organization(admin_client: APIClient):
    body = {
        "name": "none-organization",
        "url": "https://git.example.com/acme/project-01",
        "organization_id": None,
    }

    response = admin_client.post(f"{api_url_v1}/projects/", data=body)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Organization is needed" in str(response.data)


@pytest.mark.django_db
def test_create_project_name_conflict(
    default_project: models.Project, admin_client: APIClient
):
    response = admin_client.post(
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


@pytest.mark.django_db
@mock.patch("aap_eda.core.tasking.is_redis_failed", return_value=True)
@mock.patch("aap_eda.tasks.import_project")
def test_create_project_redis_unavailable(
    import_project_task: mock.Mock,
    is_redis_failed: mock.Mock,
    admin_client: APIClient,
    default_scm_credential,
    default_organization: models.Organization,
    preseed_credential_types,
):
    def raise_connection_error(*args, **kwargs):
        raise redis.ConnectionError("redis unavailable")

    import_project_task.side_effect = raise_connection_error

    credential = create_custom_credential(
        credential_type=enums.DefaultCredentialType.GPG,
        organization=default_organization,
    )

    body = {
        "name": "ain't-no-redis",
        "url": "https://git.example.com/acme/project-01",
        "eda_credential_id": default_scm_credential.id,
        "signature_validation_credential_id": credential.id,
        "scm_branch": "main",
        "scm_refspec": "path/to/ref1",
        "organization_id": default_organization.id,
    }

    response = admin_client.post(
        f"{api_url_v1}/projects/",
        data=body,
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "Redis is required but unavailable."}


@pytest.mark.django_db
def test_create_project_wrong_ids(admin_client: APIClient):
    bodies = [
        {
            "name": "test-project-01",
            "url": "https://git.example.com/acme/project-01",
            "eda_credential_id": 3000001,
        },
        {
            "name": "test-project-02",
            "url": "https://git.example.com/acme/project-01",
            "signature_validation_credential_id": 3000001,
        },
        {
            "name": "test-project-03",
            "url": "https://git.example.com/acme/project-01",
            "organization_id": 3000001,
        },
    ]

    for body in bodies:
        response = admin_client.post(
            f"{api_url_v1}/projects/",
            data=body,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "id 3000001 does not exist" in str(response.json())


@pytest.mark.django_db
def test_create_project_with_invalid_git_parameters(
    admin_client: APIClient,
    default_organization: models.Organization,
):
    body = {
        "name": "test-project-01",
        "url": "https://git.{{example}}.com/acme/project-01",
        "scm_branch": "bad branch",
        "scm_refspec": "path",
        "organization_id": default_organization.id,
    }

    response = admin_client.post(
        f"{api_url_v1}/projects/",
        data=body,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    error = str(response.json())
    assert "Invalid source control URL" in error
    assert "Invalid branch/tag/commit" in error
    assert "Invalid refspec" in error


@pytest.mark.django_db
@mock.patch(
    "aap_eda.api.views.project.RedisDependencyMixin.redis_is_available"
)
def test_create_project_with_redis_is_available(
    redis_available,
    admin_client,
    default_organization,
    preseed_credential_types,
):
    credential_type = enums.DefaultCredentialType.SOURCE_CONTROL
    credential = create_custom_credential(
        credential_type=credential_type, organization=default_organization
    )
    message = "Redis is required but unavailable"

    redis_available.side_effect = api_exc.Conflict(message)

    response = admin_client.post(
        f"{api_url_v1}/projects/",
        data={
            "name": "test-project-redis-down",
            "url": "https://git.example.com/acme/project-01",
            "eda_credential_id": credential.id,
            "organization_id": default_organization.id,
        },
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert message in response.data["detail"]


# Test: Sync project
# -------------------------------------
@pytest.mark.django_db
@mock.patch("aap_eda.tasks.sync_project")
@mock.patch(
    "aap_eda.api.views.project.RedisDependencyMixin.redis_is_available"
)
@pytest.mark.parametrize(
    "initial_state",
    [
        models.Project.ImportState.COMPLETED,
        models.Project.ImportState.FAILED,
    ],
)
def test_sync_project(
    redis_available: mock.Mock,
    sync_project_task: mock.Mock,
    admin_client: APIClient,
    initial_state: models.Project.ImportState,
    default_project: models.Project,
):
    default_project.import_state = initial_state
    default_project.save(update_fields=["import_state"])

    job_id = "3677eb4a-de4a-421a-a73b-411aa502484d"
    sync_project_task.return_value = job_id

    response = admin_client.post(
        f"{api_url_v1}/projects/{default_project.id}/sync/"
    )
    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()

    default_project.refresh_from_db()
    assert default_project.import_state == "pending"
    assert default_project.import_error is None
    assert str(default_project.import_task_id) == job_id

    assert_project_data(data, default_project)

    sync_project_task.assert_called_once_with(default_project.id)


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
    admin_client: APIClient,
    initial_state: models.Project.ImportState,
    default_project: models.Project,
):
    default_project.import_state = initial_state
    default_project.import_task_id = None
    default_project.save(update_fields=["import_state", "import_task_id"])

    response = admin_client.post(
        f"{api_url_v1}/projects/{default_project.id}/sync/"
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "detail": "Project import or sync is already running."
    }

    sync_project_task.assert_not_called()
    default_project.refresh_from_db()
    assert default_project.import_state == initial_state
    assert default_project.import_task_id is None


@pytest.mark.django_db
def test_sync_project_not_exist(admin_client: APIClient):
    response = admin_client.post(f"{api_url_v1}/projects/42/sync/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
@mock.patch("aap_eda.core.tasking.is_redis_failed", return_value=True)
@mock.patch("aap_eda.tasks.sync_project")
def test_sync_project_redis_unavailable(
    sync_project_task: mock.Mock,
    is_redis_failed: mock.Mock,
    admin_client: APIClient,
    default_project: models.Project,
):
    def raise_connection_error(*args, **kwargs):
        raise redis.ConnectionError("redis unavailable")

    sync_project_task.side_effect = raise_connection_error

    response = admin_client.post(
        f"{api_url_v1}/projects/{default_project.id}/sync/"
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "Redis is required but unavailable."}


@pytest.mark.django_db
@mock.patch(
    "aap_eda.api.views.project.RedisDependencyMixin.redis_is_available"
)
def test_sync_project_with_redis_is_available(
    redis_available, admin_client, default_project
):
    message = "Redis is required but unavailable"
    redis_available.side_effect = api_exc.Conflict(message)

    response = admin_client.post(
        f"{api_url_v1}/projects/{default_project.id}/sync/",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert message in response.data["detail"]


# Test: Partial update project
# -------------------------------------
@pytest.mark.django_db
def test_update_project_not_found(
    default_project: models.Project, admin_client: APIClient
):
    response = admin_client.get(f"{api_url_v1}/projects/{default_project.id}/")
    data = response.json()

    response = admin_client.patch(f"{api_url_v1}/projects/42/", data=data)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_update_project_with_400(
    default_project: models.Project,
    new_project: models.Project,
    admin_client: APIClient,
):
    response = admin_client.get(f"{api_url_v1}/projects/{default_project.id}/")
    data = {
        "name": new_project.name,
        "git_hash": default_project.git_hash,
    }

    # test empty string validator
    response = admin_client.patch(
        f"{api_url_v1}/projects/{default_project.id}/", data={"name": ""}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["name"][0] == "This field may not be blank."
    # test unique name validator
    response = admin_client.patch(
        f"{api_url_v1}/projects/{default_project.id}/", data=data
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["name"][0] == "Project with this name already exists."
    # test non-existent dependent object reference
    data = [
        {"eda_credential_id": 3000001},
        {"signature_validation_credential_id": 3000001},
    ]

    for update_data in data:
        response = admin_client.patch(
            f"{api_url_v1}/projects/{default_project.id}/", data=update_data
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "id 3000001 does not exist" in str(response.json())

    data = {
        "url": "https://git.{{example}}.com/acme/project-01",
        "scm_branch": "bad branch",
        "scm_refspec": "path",
    }
    response = admin_client.patch(
        f"{api_url_v1}/projects/{default_project.id}/", data=data
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    error = str(response.json())
    assert "Invalid source control URL" in error
    assert "Invalid branch/tag/commit" in error
    assert "Invalid refspec" in error


@pytest.mark.django_db
def test_partial_update_project(
    new_project: models.Project,
    default_scm_credential: models.EdaCredential,
    default_gpg_credential: models.EdaCredential,
    superuser_client: APIClient,
):
    assert new_project.eda_credential_id is None
    assert new_project.signature_validation_credential_id is None
    assert new_project.verify_ssl is False

    new_org = models.Organization.objects.create(name="new org")
    new_data = {
        "name": "new-project-updated",
        "organization_id": new_org.id,
        "eda_credential_id": default_scm_credential.id,
        "signature_validation_credential_id": default_gpg_credential.id,
        "scm_branch": "main",
        "scm_refspec": "path/to/ref1",
        "verify_ssl": True,
        "proxy": "http://user:$encrypted$@myproxy.com",
    }
    response = superuser_client.patch(
        f"{api_url_v1}/projects/{new_project.id}/",
        data=new_data,
    )
    assert response.status_code == status.HTTP_200_OK

    new_project.refresh_from_db()
    assert new_project.name == new_data["name"]
    assert new_project.organization.id == new_data["organization_id"]
    assert new_project.eda_credential.id == new_data["eda_credential_id"]
    assert (
        new_project.signature_validation_credential.id
        == new_data["signature_validation_credential_id"]
    )
    assert new_project.verify_ssl is new_data["verify_ssl"]

    assert_project_data(response.json(), new_project)


@pytest.mark.django_db
def test_partial_update_project_null_organization_id(
    default_project: models.Project, admin_client: APIClient
):
    data = {
        "organization_id": None,
    }
    response = admin_client.patch(
        f"{api_url_v1}/projects/{default_project.id}/",
        data,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Organization is needed" in str(response.data)


@pytest.mark.django_db
def test_partial_update_project_bad_proxy(
    default_project: models.Project, admin_client: APIClient
):
    data = {
        "name": "test-project-01-updated",
        "proxy": "http://new-user:$encrypted$@myproxy.com",
    }
    response = admin_client.patch(
        f"{api_url_v1}/projects/{default_project.id}/",
        data,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "The password in the proxy field should be unencrypted" in str(
        response.data
    )


@pytest.mark.django_db
def test_partial_update_project_url(
    new_project: models.Project,
    admin_client: APIClient,
):
    original_url = new_project.url
    new_url = "https://git.example.com/foo-bar"

    response = admin_client.patch(
        f"{api_url_v1}/projects/{new_project.id}/",
        data={"url": new_url},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["url"] == new_url
    assert response.json()["import_state"] == "pending"

    new_project.refresh_from_db()
    assert new_project.url == new_url
    assert new_project.url != original_url


@pytest.mark.django_db
def test_partial_update_project_scm_branch(
    new_project: models.Project,
    admin_client: APIClient,
):
    original_scm_branch = new_project.scm_branch
    new_scm_branch = "dev"

    response = admin_client.patch(
        f"{api_url_v1}/projects/{new_project.id}/",
        data={"scm_branch": new_scm_branch},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["scm_branch"] == new_scm_branch
    assert response.json()["import_state"] == "pending"

    new_project.refresh_from_db()
    assert new_project.scm_branch == new_scm_branch
    assert new_project.scm_branch != original_scm_branch


@pytest.mark.django_db
def test_partial_update_project_scm_refspec(
    new_project: models.Project,
    admin_client: APIClient,
):
    original_scm_refspec = new_project.scm_refspec
    new_scm_refspec = "path/to/testref"

    response = admin_client.patch(
        f"{api_url_v1}/projects/{new_project.id}/",
        data={"scm_refspec": new_scm_refspec},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["scm_refspec"] == new_scm_refspec
    assert response.json()["import_state"] == "pending"

    new_project.refresh_from_db()
    assert new_project.scm_refspec == new_scm_refspec
    assert new_project.scm_refspec != original_scm_refspec


@pytest.mark.django_db
def test_delete_project(
    new_project: models.Project,
    admin_client: APIClient,
):
    response = admin_client.delete(f"{api_url_v1}/projects/{new_project.id}/")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not models.Project.objects.filter(pk=new_project.id).exists()


@pytest.mark.django_db
def test_delete_project_not_found(admin_client: APIClient):
    response = admin_client.delete(f"{api_url_v1}/projects/42/")

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.import_project")
@mock.patch(
    "aap_eda.api.views.project.RedisDependencyMixin.redis_is_available"
)
def test_project_by_fields(
    redis_available: mock.Mock,
    import_project_task: mock.Mock,
    default_scm_credential: models.EdaCredential,
    default_organization: models.Organization,
    admin_user: models.User,
    super_user: models.User,
    base_client: APIClient,
):
    job_id = "3677eb4a-de4a-421a-a73b-411aa502484d"
    import_project_task.return_value = job_id

    body = {
        "name": "test-project-01",
        "url": "https://git.example.com/acme/project-01",
        "eda_credential_id": default_scm_credential.id,
        "scm_branch": "main",
        "scm_refspec": "path/to/ref1",
        "organization_id": default_organization.id,
    }

    base_client.force_authenticate(user=admin_user)
    response = base_client.post(
        f"{api_url_v1}/projects/",
        data=body,
    )
    assert response.status_code == status.HTTP_201_CREATED
    project = models.Project.objects.get(id=response.data["id"])

    assert response.data["created_by"]["username"] == admin_user.username
    assert response.data["modified_by"]["username"] == admin_user.username

    response = base_client.get(f"{api_url_v1}/projects/{response.data['id']}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["created_by"]["username"] == admin_user.username
    assert response.data["modified_by"]["username"] == admin_user.username

    response = base_client.get(f"{api_url_v1}/projects/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["results"]
    assert data[0]["created_by"]["username"] == admin_user.username
    assert data[0]["modified_by"]["username"] == admin_user.username

    base_client.force_authenticate(user=super_user)
    update_data = {"name": "test_project_by_fields"}
    response = base_client.patch(
        f"{api_url_v1}/projects/{project.id}/",
        update_data,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["created_by"]["username"] == admin_user.username
    assert response.data["modified_by"]["username"] == super_user.username

    project.refresh_from_db()
    assert project.created_by == admin_user
    assert project.modified_by == super_user


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
        elif isinstance(project_value, models.Organization):
            assert value == get_organization_details(project_value)
        else:
            if key == "proxy":
                project_value = project_value.get_secret_value().replace(
                    "secret", "$encrypted$"
                )

            if key == "created_by" or key == "modified_by":
                project_value = BasicUserSerializer(project_value).data

            assert value == project_value


def get_credential_details(credential: models.EdaCredential) -> dict:
    credential.refresh_from_db()
    return {
        "id": credential.id,
        "name": credential.name,
        "description": credential.description,
        "credential_type_id": credential.credential_type.id,
        "organization_id": credential.organization.id,
        "managed": credential.managed,
        "inputs": inputs_to_display(
            credential.credential_type.inputs,
            credential.inputs.get_secret_value(),
        ),
    }


def get_organization_details(organization: models.Organization) -> dict:
    organization.refresh_from_db()
    return {
        "id": organization.id,
        "name": organization.name,
        "description": organization.description,
    }


def create_custom_credential(
    credential_type: enums.CredentialType, organization: models.Organization
) -> models.EdaCredential:
    cred_inputs = inputs_to_store({"user": "me"})
    credential_type = models.CredentialType.objects.get(name=credential_type)
    return models.EdaCredential.objects.create(
        name="custom-credential",
        description="Custom Credential",
        credential_type=credential_type,
        inputs=cred_inputs,
        organization=organization,
    )
