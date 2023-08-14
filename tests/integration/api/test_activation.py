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
from aap_eda.core.enums import (
    Action,
    ActivationStatus,
    ResourceType,
    RestartPolicy,
)
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

TEST_AWX_TOKEN = {
    "name": "test-awx-token",
    "description": "test AWX token",
    "token": "abc123xyx",
}

TEST_AWX_TOKEN_2 = {
    "name": "test-awx-token-2",
    "description": "test AWX token",
    "token": "abc123xyx",
}

TEST_PROJECT = {
    "git_hash": "684f62df18ce5f8d5c428e53203b9b975426eed0",
    "name": "test-project-01",
    "url": "https://git.example.com/acme/project-01",
    "description": "test project",
}

TEST_RULEBOOK = {
    "name": "test-rulebook.yml",
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
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    user_id = user.pk
    models.AwxToken.objects.create(
        name=TEST_AWX_TOKEN["name"],
        token=TEST_AWX_TOKEN["token"],
        user=user,
    )
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


def create_multiple_activations(fks: dict):
    activation_names = ["test-activation", "filter-test-activation"]
    statuses = [ActivationStatus.COMPLETED, ActivationStatus.FAILED]
    activations = []
    for name, _status in zip(activation_names, statuses):
        activation_data = {
            "name": name,
            "description": "test activation",
            "is_enabled": True,
            "decision_environment_id": fks["decision_environment_id"],
            "project_id": fks["project_id"],
            "rulebook_id": fks["project_id"],
            "extra_var_id": fks["project_id"],
            "user_id": fks["user_id"],
            "status": _status,
            "restart_policy": RestartPolicy.ON_FAILURE.value,
            "restart_count": 0,
        }
        activation = models.Activation(**activation_data)
        activations.append(activation)
        activation.save()

    return activations


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

    client.post(f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN)
    response = client.post(f"{api_url_v1}/activations/", data=test_activation)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.data
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert_activation_base_data(
        data,
        activation,
    )
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
    assert activation.rulebook_name == TEST_RULEBOOK["name"]
    assert activation.rulebook_rulesets == TEST_RULESETS
    assert data["restarted_at"] is None


@pytest.mark.django_db
def test_create_activation_disabled(client: APIClient):
    fks = create_activation_related_data()
    test_activation = TEST_ACTIVATION.copy()
    test_activation["is_enabled"] = False
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["project_id"] = fks["project_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["extra_var_id"] = fks["extra_var_id"]

    client.post(f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN)
    response = client.post(f"{api_url_v1}/activations/", data=test_activation)
    assert response.status_code == status.HTTP_201_CREATED
    response = client.get(f"{api_url_v1}/activations/{response.data['id']}/")
    data = response.data
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert activation.rulebook_name == TEST_RULEBOOK["name"]
    assert activation.rulebook_rulesets == TEST_RULESETS
    assert data["status"] == ActivationStatus.PENDING.value
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


@pytest.mark.parametrize(
    "dependent_object",
    ["decision_environment", "project", "rulebook", "extra_var"],
)
@pytest.mark.django_db(transaction=True)
def test_create_activation_unprocessible_entity(
    client: APIClient, dependent_object, check_permission_mock: mock.Mock
):
    fks = create_activation_related_data()
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["project_id"] = fks["project_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["extra_var_id"] = fks["extra_var_id"]

    client.post(f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN)
    response = client.post(
        f"{api_url_v1}/activations/",
        data={
            **test_activation,
            f"{dependent_object}_id": 0,
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert (
        response.data["detail"]
        == f"{dependent_object.capitalize()} with ID=0 does not exist."
    )

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.ACTIVATION, Action.CREATE
    )


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
def test_list_activations_filter_name(client: APIClient):
    filter_name = "filter"
    fks = create_activation_related_data()
    activations = create_multiple_activations(fks)

    response = client.get(f"{api_url_v1}/activations/?name={filter_name}")
    assert response.status_code == status.HTTP_200_OK
    response_data = response.data["results"]
    assert_activation_base_data(response_data[0], activations[1])


@pytest.mark.django_db
def test_list_activations_filter_name_none_exist(client: APIClient):
    filter_name = "noname"
    fks = create_activation_related_data()
    create_multiple_activations(fks)

    response = client.get(f"{api_url_v1}/activations/?name={filter_name}")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["results"] == []


@pytest.mark.django_db
def test_list_activations_filter_status(client: APIClient):
    filter_status = "failed"
    fks = create_activation_related_data()
    activations = create_multiple_activations(fks)

    response = client.get(f"{api_url_v1}/activations/?status={filter_status}")
    assert response.status_code == status.HTTP_200_OK
    response_data = response.data["results"]
    assert_activation_base_data(response_data[0], activations[1])


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
    activation_instances = models.ActivationInstance.objects.filter(
        activation_id=activation.id
    )
    if activation_instances:
        assert data["restarted_at"] == activation_instances.latest(
            "started_at"
        ).started_at.strftime(DATETIME_FORMAT)
    else:
        assert data["restarted_at"] is None


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
@mock.patch("aap_eda.tasks.ruleset.deactivate.delay")
def test_disable_activation(delay_mock: mock.Mock, client: APIClient):
    fks = create_activation_related_data()
    activation = create_activation(fks)

    response = client.post(
        f"{api_url_v1}/activations/{activation.id}/disable/"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_list_activation_instances(client: APIClient):
    fks = create_activation_related_data()
    activation = create_activation(fks)
    instances = models.ActivationInstance.objects.bulk_create(
        [
            models.ActivationInstance(
                name="test-activation-instance-1",
                activation=activation,
            ),
            models.ActivationInstance(
                name="test-activation-instance-1",
                activation=activation,
            ),
        ]
    )
    response = client.get(
        f"{api_url_v1}/activations/{activation.id}/instances/"
    )
    data = response.data["results"]
    assert response.status_code == status.HTTP_200_OK
    assert len(data) == len(instances)
    assert data[0]["name"] == instances[0].name
    assert data[1]["name"] == instances[1].name


@pytest.mark.django_db
def test_list_activation_instances_filter_name(client: APIClient):
    fks = create_activation_related_data()
    activation = create_activation(fks)
    instances = models.ActivationInstance.objects.bulk_create(
        [
            models.ActivationInstance(
                name="activation-instance-1",
                activation=activation,
            ),
            models.ActivationInstance(
                name="test-activation-instance-2",
                activation=activation,
            ),
        ]
    )

    filter_name = "instance-1"
    response = client.get(
        f"{api_url_v1}/activations/{activation.id}"
        f"/instances/?name={filter_name}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["name"] == instances[0].name


@pytest.mark.django_db
def test_list_activation_instances_filter_status(client: APIClient):
    fks = create_activation_related_data()
    activation = create_activation(fks)
    instances = models.ActivationInstance.objects.bulk_create(
        [
            models.ActivationInstance(
                name="activation-instance-1",
                status="completed",
                activation=activation,
            ),
            models.ActivationInstance(
                name="test-activation-instance-2",
                status="failed",
                activation=activation,
            ),
        ]
    )

    filter_status = "failed"
    response = client.get(
        f"{api_url_v1}/activations/{activation.id}"
        f"/instances/?status={filter_status}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["name"] == instances[1].name
    assert response.data["results"][0]["status"] == filter_status


DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def assert_activation_base_data(
    data: Dict[str, Any], activation: models.Activation
):
    rules_count, rules_fired_count = _get_rules_count(activation.ruleset_stats)
    assert data["id"] == activation.id
    assert data["name"] == activation.name
    assert data["description"] == activation.description
    assert data["is_enabled"] == activation.is_enabled
    assert data["restart_policy"] == activation.restart_policy
    assert data["restart_count"] == activation.restart_count
    assert data["rulebook_name"] == activation.rulebook_name
    assert data["rules_count"] == rules_count
    assert data["rules_fired_count"] == rules_fired_count
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


def _get_rules_count(ruleset_stats):
    rules_count = 0
    rules_fired_count = 0
    for ruleset_stat in ruleset_stats.values():
        rules_count += ruleset_stat["numberOfRules"]
        rules_fired_count += ruleset_stat["rulesTriggered"]

    return rules_count, rules_fired_count


@pytest.mark.django_db
def test_create_activation_no_token(client: APIClient):
    fks = create_activation_related_data()
    test_activation = TEST_ACTIVATION.copy()
    test_activation["is_enabled"] = True
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["project_id"] = fks["project_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["extra_var_id"] = fks["extra_var_id"]

    response = client.post(f"{api_url_v1}/activations/", data=test_activation)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert str(response.data["detail"]) == "No controller token specified"


@pytest.mark.django_db
def test_create_activation_more_tokens(client: APIClient):
    fks = create_activation_related_data()
    test_activation = TEST_ACTIVATION.copy()
    test_activation["is_enabled"] = True
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["project_id"] = fks["project_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["extra_var_id"] = fks["extra_var_id"]

    client.post(f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN)
    client.post(f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN_2)
    response = client.post(f"{api_url_v1}/activations/", data=test_activation)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert (
        str(response.data["detail"])
        == "More than one controller token found, "
        "currently only 1 token is supported"
    )
