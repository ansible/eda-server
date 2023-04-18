import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.constants import api_url_v1

TEST_PLAYBOOK = """
---
- name: Test playbook
  hosts: all
  tasks: []
""".strip()


@pytest.mark.django_db
def test_list_playbooks(client: APIClient):
    obj = models.Playbook.objects.create(
        name="test-playbook.yml", playbook=TEST_PLAYBOOK
    )
    response = client.get(f"{api_url_v1}/playbooks/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["results"] == [
        {
            "id": obj.id,
            "project": None,
            "name": "test-playbook.yml",
            "playbook": TEST_PLAYBOOK,
        }
    ]


@pytest.mark.django_db
def test_retrieve_playbook(client: APIClient):
    obj = models.Playbook.objects.create(
        name="test-playbook.yml", playbook=TEST_PLAYBOOK
    )
    response = client.get(f"{api_url_v1}/playbooks/{obj.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        "id": obj.id,
        "project": None,
        "name": "test-playbook.yml",
        "playbook": TEST_PLAYBOOK,
    }


@pytest.mark.django_db
def test_retrieve_playbook_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/playbooks/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_create_playbook_not_allowed(client: APIClient):
    data_in = {
        "name": "test-playbook.yml",
        "playbook": TEST_PLAYBOOK,
    }
    response = client.post(f"{api_url_v1}/playbooks/", data=data_in)
    # NOTE(cutwater): The resource code is 403 Forbidden here, because
    #   permission checks are executed in DRF before the view method
    #   is resolved for the HTTP request. Instead of adding special case
    #   in RoleBasedPermission, we will return 403 Forbidden for now.
    #   This behavior may be revisited in future.
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_destroy_playbook_not_allowed(client: APIClient):
    obj = models.Playbook.objects.create(
        name="test-playbook.yml", playbook=TEST_PLAYBOOK
    )
    response = client.delete(f"{api_url_v1}/playbooks/{obj.id}/")
    assert response.status_code == status.HTTP_403_FORBIDDEN
