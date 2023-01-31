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

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from aap_eda.core.enums import RestartPolicy

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


def create_activation_related_data():
    project_id = models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/acme/project-01",
        git_hash="4673c67547cf6fe6a223a9dd49feb1d5f953449c",
    ).pk
    rulebook_id = models.Rulebook.objects.create(
        name="test-rulebook.yml", rulesets="..."
    ).pk
    extra_var_id = models.ExtraVar.objects.create(
        name="test-extra-var.yml", extra_var="..."
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
def test_list_activations(client: APIClient):
    fks = create_activation_related_data()
    activations = [create_activation(fks)]

    response = client.get("/eda/api/v1/activations")
    assert response.status_code == status.HTTP_200_OK
    for data, activation in zip(response.data, activations):
        assert_activation_data(data, activation, mode="list")


@pytest.mark.django_db
def test_retrieve_activation(client: APIClient):
    fks = create_activation_related_data()
    activation = create_activation(fks)

    response = client.get(f"/eda/api/v1/activations/{activation.id}")
    assert response.status_code == status.HTTP_200_OK
    assert_activation_data(response.data, activation, mode="retrieve")


@pytest.mark.django_db
def test_retrieve_activation_not_exist(client: APIClient):
    response = client.get("/eda/api/v1/activations/77")
    assert response.status_code == status.HTTP_404_NOT_FOUND


DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def assert_activation_data(
    data: Dict[str, Any], activation: models.Activation, mode: str
):
    data_dict = dict(data)
    assert data_dict["id"] == activation.id
    assert data_dict["name"] == activation.name
    assert data_dict["description"] == activation.description
    assert data_dict["is_enabled"] == activation.is_enabled
    assert data_dict["working_directory"] == activation.working_directory
    assert (
        data_dict["execution_environment"] == activation.execution_environment
    )
    assert data_dict["restart_policy"] == activation.restart_policy
    assert data_dict["restart_count"] == activation.restart_count
    assert data_dict["created_at"] == activation.created_at.strftime(
        DATETIME_FORMAT
    )
    assert data_dict["modified_at"] == activation.modified_at.strftime(
        DATETIME_FORMAT
    )
    if mode == "list":
        project_id = data_dict["project"]
        rulebook_id = data_dict["rulebook"]
        extra_var_id = data_dict["extra_var"]
    elif mode == "retrieve":
        project_id = data_dict["project"]["id"]
        rulebook_id = data_dict["rulebook"]["id"]
        extra_var_id = data_dict["extra_var"]["id"]
    assert project_id == activation.project.id
    assert rulebook_id == activation.rulebook.id
    assert extra_var_id == activation.extra_var.id
