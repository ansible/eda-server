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
import json
from typing import Any, Dict

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from aap_eda.core.enums import RestartPolicy
from tests.integration.constants import api_url_v1

TEST_ACTIVATION = {
    "name": "test-activation",
    "description": "test activation",
    "is_enabled": True,
    "working_directory": "/tmp",
    "execution_environment": "quay.io/aizquier/ansible-rulebook",
    "project_id": 1,
    "rulebook_id": 1,
    "extra_var_id": 1,
    "restart_policy": RestartPolicy.ON_FAILURE.value,
    "restart_count": 0,
}

TEST_PROJECT = {
    "name": "test-project-01",
    "url": "https://git.example.com/acme/project-01",
    "description": "test project",
}

TEST_RULEBOOK = {
    "name": "test-rulebook.yml",
    "description": "test rulebok",
}

TEST_RULESETS = """
---
- name: hello
  hosts: localhost
  gather_facts: false
  tasks:
    - debug:
        msg: hello
"""

TEST_EXTRA_VAR = """
---
collections:
  - community.general
  - benthomasson.eda
"""


def create_activation_related_data():
    project_id = models.Project.objects.create(
        name=TEST_PROJECT["name"],
        url=TEST_PROJECT["url"],
        description=TEST_PROJECT["description"],
    ).pk
    rulebook_id = models.Rulebook.objects.create(
        name=TEST_RULEBOOK["name"],
        rulesets=TEST_RULESETS,
        description=TEST_RULEBOOK["description"],
    ).pk
    extra_var_id = models.ExtraVar.objects.create(
        name="test-extra-var.yml", extra_var=TEST_EXTRA_VAR
    ).pk

    return {
        "project_id": project_id,
        "rulebook_id": rulebook_id,
        "extra_var_id": extra_var_id,
    }


def create_activation(fks: dict):
    activation_data = TEST_ACTIVATION.copy()
    activation_data["project_id"] = fks["project_id"]
    activation_data["rulebook_id"] = fks["rulebook_id"]
    activation_data["extra_var_id"] = fks["extra_var_id"]
    activation = models.Activation(**activation_data)
    activation.save()

    return activation


@pytest.mark.django_db
def test_create_activation(client: APIClient):
    fks = create_activation_related_data()
    test_activation = TEST_ACTIVATION.copy()
    test_activation["project_id"] = fks["project_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["extra_var_id"] = fks["extra_var_id"]

    response = client.post(f"{api_url_v1}/activations/", data=test_activation)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.data
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert_activation_base_data(
        data,
        activation,
    )
    assert_activation_related_object_fks(data, activation)


@pytest.mark.django_db
def test_create_activation_bad_entity(client: APIClient):
    test_activation = {
        "name": "test-activation",
        "description": "test activation",
        "is_enabled": True,
    }
    response = client.post(
        f"{api_url_v1}/activations/",
        data=test_activation,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_update_activation(client: APIClient):
    fks = create_activation_related_data()
    activation = create_activation(fks)
    new_activation = {
        "name": "new demo",
        "description": "demo activation",
        "is_enabled": False,
    }

    response = client.patch(
        f"{api_url_v1}/activations/{activation.id}/",
        data=json.dumps(new_activation),
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_200_OK
    activation = response.data
    assert activation["name"] == new_activation["name"]
    assert activation["description"] == new_activation["description"]
    assert activation["is_enabled"] == new_activation["is_enabled"]


@pytest.mark.django_db
def test_list_activations(client: APIClient):
    fks = create_activation_related_data()
    activations = [create_activation(fks)]

    response = client.get(f"{api_url_v1}/activations/")
    assert response.status_code == status.HTTP_200_OK
    for data, activation in zip(response.data["results"], activations):
        assert_activation_base_data(data, activation)
        assert_activation_related_object_fks(data, activation)


@pytest.mark.django_db
def test_retrieve_activation(client: APIClient):
    fks = create_activation_related_data()
    activation = create_activation(fks)

    response = client.get(f"{api_url_v1}/activations/{activation.id}/")
    assert response.status_code == status.HTTP_200_OK
    data = response.data
    assert_activation_base_data(data, activation)
    assert data["project"] == {"id": activation.project.id, **TEST_PROJECT}
    assert data["rulebook"] == {"id": activation.rulebook.id, **TEST_RULEBOOK}
    assert data["extra_var"] == {
        "id": activation.extra_var.id,
        "name": "test-extra-var.yml",
    }


@pytest.mark.django_db
def test_retrieve_activation_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/activations/77/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_delete_activation(client: APIClient):
    fks = create_activation_related_data()
    activation = create_activation(fks)

    response = client.delete(f"{api_url_v1}/activations/{activation.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT


DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def assert_activation_base_data(
    data: Dict[str, Any], activation: models.Activation
):
    assert data["id"] == activation.id
    assert data["name"] == activation.name
    assert data["description"] == activation.description
    assert data["is_enabled"] == activation.is_enabled
    assert data["working_directory"] == activation.working_directory
    assert data["execution_environment"] == activation.execution_environment
    assert data["restart_policy"] == activation.restart_policy
    assert data["restart_count"] == activation.restart_count
    assert data["created_at"] == activation.created_at.strftime(
        DATETIME_FORMAT
    )
    assert data["modified_at"] == activation.modified_at.strftime(
        DATETIME_FORMAT
    )


def assert_activation_related_object_fks(
    data: Dict[str, Any], activation: models.Activation
):
    assert data["project_id"] == activation.project.id
    assert data["rulebook_id"] == activation.rulebook.id
    assert data["extra_var_id"] == activation.extra_var.id
