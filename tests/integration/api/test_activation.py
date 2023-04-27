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
from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.api import serializers
from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus, RestartPolicy
from tests.integration.constants import api_url_v1

TEST_ACTIVATION = {
    "name": "test-activation",
    "description": "test activation",
    "is_enabled": True,
    "decision_environment_id": 1,
    "project_id": 1,
    "rulebook_id": 1,
    "extra_var_id": 1,
    "restart_policy": RestartPolicy.ON_FAILURE.value,
    "restart_count": 0,
}

TEST_PROJECT = {
    "git_hash": "684f62df18ce5f8d5c428e53203b9b975426eed0",
    "name": "test-project-01",
    "url": "https://git.example.com/acme/project-01",
    "description": "test project",
}

TEST_RULEBOOK = {
    "name": "test-rulebook.yml",
    "path": "rulebooks",
    "description": "test rulebook",
}

TEST_DECISION_ENV = {
    "name": "test-de",
    "description": "test de",
    "image_url": "quay.io/ansible/ansible-rulebook",
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


def create_activation_related_data(with_project=True):
    user_id = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    ).pk
    decision_environment_id = models.DecisionEnvironment.objects.create(
        name=TEST_DECISION_ENV["name"],
        image_url=TEST_DECISION_ENV["image_url"],
        description=TEST_DECISION_ENV["description"],
    ).pk
    project_id = (
        models.Project.objects.create(
            git_hash=TEST_PROJECT["git_hash"],
            name=TEST_PROJECT["name"],
            url=TEST_PROJECT["url"],
            description=TEST_PROJECT["description"],
        ).pk
        if with_project
        else None
    )
    rulebook_id = (
        models.Rulebook.objects.create(
            name=TEST_RULEBOOK["name"],
            path=TEST_RULEBOOK["path"],
            rulesets=TEST_RULESETS,
            description=TEST_RULEBOOK["description"],
        ).pk
        if with_project
        else None
    )
    extra_var_id = models.ExtraVar.objects.create(extra_var=TEST_EXTRA_VAR).pk

    return {
        "user_id": user_id,
        "decision_environment_id": decision_environment_id,
        "project_id": project_id,
        "rulebook_id": rulebook_id,
        "extra_var_id": extra_var_id,
    }


def create_activation(fks: dict):
    activation_data = TEST_ACTIVATION.copy()
    activation_data["decision_environment_id"] = fks["decision_environment_id"]
    activation_data["project_id"] = fks["project_id"]
    activation_data["rulebook_id"] = fks["rulebook_id"]
    activation_data["extra_var_id"] = fks["extra_var_id"]
    activation_data["user_id"] = fks["user_id"]
    activation = models.Activation(**activation_data)
    activation.save()

    return activation


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.activate_rulesets")
def test_create_activation(activate_rulesets: mock.Mock, client: APIClient):
    job = mock.Mock()
    activate_rulesets.delay.return_value = job

    fks = create_activation_related_data()
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
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
    assert activation.rulebook_name == TEST_RULEBOOK["name"]
    assert activation.rulebook_rulesets == TEST_RULESETS


@pytest.mark.django_db
def test_create_activation_disabled(client: APIClient):
    fks = create_activation_related_data()
    test_activation = TEST_ACTIVATION.copy()
    test_activation["is_enabled"] = False
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["project_id"] = fks["project_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["extra_var_id"] = fks["extra_var_id"]

    response = client.post(f"{api_url_v1}/activations/", data=test_activation)
    assert response.status_code == status.HTTP_201_CREATED
    response = client.get(f"{api_url_v1}/activations/{response.data['id']}/")
    data = response.data
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert activation.rulebook_name == TEST_RULEBOOK["name"]
    assert activation.rulebook_rulesets == TEST_RULESETS
    assert data["status"] == ActivationStatus.STOPPED.value
    assert not data["instances"]


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


@pytest.mark.django_db(transaction=True)
def test_create_activation_unprocessible_entity(client: APIClient):
    test_activation = {
        "name": "test-activation",
        "description": "test activation",
        "is_enabled": True,
        "decision_environment_id": 32,
        "rulebook_id": 100,
    }

    with mock.patch.object(
        serializers.ActivationCreateSerializer,
        "create",
        mock.Mock(side_effect=IntegrityError),
    ):
        response = client.post(
            f"{api_url_v1}/activations/",
            data=test_activation,
        )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


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
@pytest.mark.parametrize("with_project", [True, False])
def test_retrieve_activation(client: APIClient, with_project):
    fks = create_activation_related_data(with_project)
    activation = create_activation(fks)

    response = client.get(f"{api_url_v1}/activations/{activation.id}/")
    assert response.status_code == status.HTTP_200_OK
    data = response.data
    assert_activation_base_data(data, activation)
    if activation.project:
        assert data["project"] == {"id": activation.project.id, **TEST_PROJECT}
    else:
        assert not data["project"]
    if activation.rulebook:
        assert data["rulebook"] == {
            "id": activation.rulebook.id,
            **TEST_RULEBOOK,
        }
    else:
        assert not data["rulebook"]
    assert data["decision_environment"] == {
        "id": activation.decision_environment.id,
        **TEST_DECISION_ENV,
    }
    assert data["extra_var"] == {
        "id": activation.extra_var.id,
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


@pytest.mark.django_db
def test_restart_activation(client: APIClient):
    fks = create_activation_related_data()
    activation = create_activation(fks)

    response = client.post(
        f"{api_url_v1}/activations/{activation.id}/restart/"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_enable_activation(client: APIClient):
    fks = create_activation_related_data()
    activation = create_activation(fks)

    response = client.post(f"{api_url_v1}/activations/{activation.id}/enable/")

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_disable_activation(client: APIClient):
    fks = create_activation_related_data()
    activation = create_activation(fks)

    response = client.post(
        f"{api_url_v1}/activations/{activation.id}/disable/"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT


DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def assert_activation_base_data(
    data: Dict[str, Any], activation: models.Activation
):
    assert data["id"] == activation.id
    assert data["name"] == activation.name
    assert data["description"] == activation.description
    assert data["is_enabled"] == activation.is_enabled
    assert data["restart_policy"] == activation.restart_policy
    assert data["restart_count"] == activation.restart_count
    assert data["rulebook_name"] == activation.rulebook_name
    assert data["created_at"] == activation.created_at.strftime(
        DATETIME_FORMAT
    )
    assert data["modified_at"] == activation.modified_at.strftime(
        DATETIME_FORMAT
    )


def assert_activation_related_object_fks(
    data: Dict[str, Any], activation: models.Activation
):
    if activation.project:
        assert data["project_id"] == activation.project.id
    else:
        assert not data["project_id"]
    if activation.rulebook:
        assert data["rulebook_id"] == activation.rulebook.id
    else:
        assert not data["rulebook_id"]
    assert data["extra_var_id"] == activation.extra_var.id
    assert (
        data["decision_environment_id"] == activation.decision_environment.id
    )
