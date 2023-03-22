from http import HTTPStatus
from time import sleep

import nanoid
import pytest

from eda_api.model.project import Project
from eda_qa.api import api_client
from eda_qa.api.projects import ProjectImportStates
from eda_qa.config import config
from eda_qa.utils.projects import wait_for_project_import


@pytest.mark.qa
@pytest.mark.api
def test_list_projects(new_project: Project):
    """
    Test the correct listing of projects
    """
    projects = []
    for response in api_client.projects.iter_pages():
        assert response.status_code == HTTPStatus.OK
        projects.extend(response.data.results)

    assert len([project for project in projects if project.id == new_project.id]) == 1


@pytest.mark.timeout(config.default_timeout)
@pytest.mark.qa
@pytest.mark.api
def test_create_project(teardown_projects):
    """
    Test the correct creation of a project
    """
    payload = {
        "name": f"QE-test-{nanoid.generate()}",
        "description": "Test project created by QE",
    }
    response = api_client.projects.create(**payload)
    teardown_projects(response.data)
    assert response.status_code == HTTPStatus.CREATED
    assert response.data.import_state == ProjectImportStates.PENDING

    while True:
        project = api_client.projects.read(response.data.id)
        if project.data.import_state == ProjectImportStates.COMPLETED:
            break
        sleep(0.1)

    assert project.status_code == HTTPStatus.OK

    assert project.data.name == payload["name"]
    assert project.data.description == payload["description"]
    assert project.data.url == config.default_project_url


@pytest.mark.qa
@pytest.mark.api
def test_create_project_duplicated(teardown_projects):
    """
    Test the creation of a project name that already exists
    """
    payload = {
        "name": f"QE-test-{nanoid.generate()}",
        "description": "Test project created by QE",
    }
    response = api_client.projects.create(**payload)
    assert response.status_code == HTTPStatus.CREATED

    project = wait_for_project_import(response.data.id)

    project_id = project.data.id
    teardown_projects(project_id)

    response = api_client.projects.create(**payload)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "project with this name already exists." in response.data


@pytest.mark.qa
@pytest.mark.api
def test_read_project(new_project: Project):
    """
    Test the correct fetch of a project
    """
    response = api_client.projects.read(new_project.id)

    assert response.status_code == HTTPStatus.OK
    assert response.data.id == new_project.id
    assert response.data.name == new_project.name
    assert response.data.description == new_project.description
    assert response.data.url == new_project.url


@pytest.mark.qa
@pytest.mark.api
@pytest.mark.xfail(reason="https://issues.redhat.com/browse/AAP-9882")
def test_delete_project(new_project: Project):
    """
    Test the correct deletion of a project
    """
    # TODO: delete project must be updated in two stages
    # First to test the deletion of a wrongly imported project
    # Later to test the deletion of any succesful project
    # Ref: https://issues.redhat.com/browse/AAP-9882

    response = api_client.projects.delete(new_project.id)
    assert response.status_code == HTTPStatus.NO_CONTENT

    response = api_client.projects.read(new_project.id)
    assert response.status_code == HTTPStatus.NOT_FOUND

    # TODO: verify related objects are deleted when it's supported


@pytest.mark.qa
@pytest.mark.api
def test_update_project(new_project: Project):
    """
    Test the correct update of a project
    """

    name = new_project.name + "-updated"
    desc = new_project.description + "-updated"
    response = api_client.projects.update(new_project.id, name, desc)

    # Verify response
    assert response.status_code == HTTPStatus.OK
    assert response.data.id == new_project.id
    assert response.data.name == name
    assert response.data.description == desc

    # Verify db record
    project = api_client.projects.read(new_project.id).data
    assert project.name == name
    assert project.description == desc

    # Test fields separately
    fields = ["name", "description"]
    for field in fields:
        new_value = {field: new_project[field] + "-2nd-update"}
        response = api_client.projects.update(new_project.id, **new_value)

        # Verify response
        assert response.status_code == 200
        assert response.data.id == new_project.id
        assert response.data[field] == new_value[field]

        # Verify db record
        project = api_client.projects.read(new_project.id).data
        assert project[field] == new_value[field]


@pytest.mark.qa
@pytest.mark.api
def test_update_project_no_changes(new_project: Project):
    """
    Test the correct update of a project when the payload has not changes
    """

    response = api_client.projects.update(
        new_project.id, name=new_project.name, description=new_project.description
    )

    # Verify response
    assert response.status_code == HTTPStatus.OK
    assert response.data.id == new_project.id
    assert response.data.name == new_project.name
    assert response.data.description == new_project.description


@pytest.mark.qa
@pytest.mark.api
def test_update_project_duplicated_name(new_project: Project, teardown_projects):
    """
    Test the update of a project with duplicated name
    """
    response = api_client.projects.create()
    project = wait_for_project_import(response.data.id)
    existing_project = project.data
    teardown_projects(existing_project)

    response = api_client.projects.update(new_project.id, existing_project.name)

    # Verify response
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "project with this name already exists." in response.data


@pytest.mark.qa
@pytest.mark.api
def test_create_update_project_empty_name(new_project: Project, teardown_projects):
    """
    Test that can not be created or updated a project with an empty name
    """
    error_msg = "This field may not be blank."

    response = api_client.projects.create(name="")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert error_msg in response.data

    response = api_client.projects.update(new_project.id, "")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert error_msg in response.data


@pytest.mark.qa
@pytest.mark.api
def test_filter_project_name(factory_new_project_batch):
    """
    Test that a list of projects can be filtered based on the name
    """

    # create two batches of projects
    batch_1 = factory_new_project_batch(prefix="QE-Batch")
    factory_new_project_batch(prefix="Batch-QE", batch_size=2)

    # filter for a single project from batch 1
    project_name = batch_1[0].name
    search_string = project_name.split("_")[0].lower()

    response = api_client.projects.list(name=search_string)
    assert response.status_code == HTTPStatus.OK
    assert response.data.count == 1
    assert response.data.results[0].name == project_name

    # filter for multiple projects
    search_string = "qE-baT"

    response = api_client.projects.list(name=search_string)
    assert response.status_code == HTTPStatus.OK
    # TODO: uncomment this line when project teardown is functioning
    # assert response.data.count == 3  # noqa: E800


@pytest.mark.qa
@pytest.mark.api
def test_filter_project_url(factory_new_project_batch):
    """
    Test that a list of projects can be filtered based on the url
    """

    # create two batches of projects, one with a different URL
    secondary_repo = "https://github.com/ttuffin/eda-sample-project"
    factory_new_project_batch()
    factory_new_project_batch(project_url=secondary_repo, batch_size=2)

    # filter for multiple projects using secondary repo url
    search_string = secondary_repo.split("-")[0]

    response = api_client.projects.list(url=search_string)
    assert response.status_code == HTTPStatus.OK
    # TODO: uncomment these lines when project teardown is functioning
    # assert response.data.count == 2  # noqa: E800
    # assert response.data.results[0].url == secondary_repo  # noqa: E800
