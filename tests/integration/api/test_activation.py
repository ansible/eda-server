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

from aap_eda.api.serializers.activation import (
    get_rules_count,
    is_activation_valid,
)
from aap_eda.core import models
from aap_eda.core.enums import (
    ACTIVATION_STATUS_MESSAGE_MAP,
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
    "restart_policy": RestartPolicy.ON_FAILURE,
    "restart_count": 0,
    "status_message": "",
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

PROJECT_GIT_HASH = "684f62df18ce5f8d5c428e53203b9b975426eed0"

TEST_PROJECT = {
    "git_hash": PROJECT_GIT_HASH,
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
    credential_id = models.Credential.objects.create(
        name="test-credential",
        description="test credential",
        credential_type="Container Registry",
        username="dummy-user",
        secret="dummy-password",
    ).pk
    decision_environment_id = models.DecisionEnvironment.objects.create(
        name=TEST_DECISION_ENV["name"],
        image_url=TEST_DECISION_ENV["image_url"],
        description=TEST_DECISION_ENV["description"],
        credential_id=credential_id,
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
            project_id=project_id,
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
        "credential_id": credential_id,
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
            "restart_policy": RestartPolicy.ON_FAILURE,
            "restart_count": 0,
        }
        activation = models.Activation(**activation_data)
        activations.append(activation)
        activation.save()

    return activations


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.activate")
def test_create_activation(activate_rulesets: mock.Mock, client: APIClient):
    job = mock.Mock()
    job.id = "8472ff2c-6045-4418-8d4e-46f6cffc8557"
    activate_rulesets.return_value = job

    fks = create_activation_related_data()
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
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
    assert activation.current_job_id == job.id
    assert activation.status == ActivationStatus.PENDING
    assert (
        activation.status_message
        == ACTIVATION_STATUS_MESSAGE_MAP[activation.status]
    )


@pytest.mark.django_db
def test_create_activation_disabled(client: APIClient):
    fks = create_activation_related_data()
    test_activation = TEST_ACTIVATION.copy()
    test_activation["is_enabled"] = False
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
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
    assert activation.status == ActivationStatus.PENDING
    assert activation.status_message == "Activation is marked as disabled"
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
    [
        {
            "decision_environment": "DecisionEnvironment with id 0 does not exist"  # noqa: E501
        },
        {"rulebook": "Rulebook with id 0 does not exist"},
        {"extra_var": "ExtraVar with id 0 does not exist"},
    ],
)
@pytest.mark.django_db(transaction=True)
def test_create_activation_with_bad_entity(
    client: APIClient, dependent_object, check_permission_mock: mock.Mock
):
    fks = create_activation_related_data()
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["extra_var_id"] = fks["extra_var_id"]

    client.post(f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN)
    for key in dependent_object:
        response = client.post(
            f"{api_url_v1}/activations/",
            data={
                **test_activation,
                f"{key}_id": 0,
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = f"'{key}_id': '{dependent_object[key]}'"
        assert str(response.data["errors"]) == "{%s}" % error

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
def test_list_activations_filter_decision_environment_id(client: APIClient):
    fks = create_activation_related_data()
    activations = create_multiple_activations(fks)
    de_id = fks["decision_environment_id"]

    response = client.get(
        f"{api_url_v1}/activations/?decision_environment_id={de_id}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == len(activations)

    response = client.get(
        f"{api_url_v1}/activations/?decision_environment_id=0"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 0


@pytest.mark.django_db
def test_list_activations_filter_credential_id(client: APIClient) -> None:
    """Test filtering by credential_id."""
    # TODO(alex): Refactor the presetup, it should be fixtures
    fks = create_activation_related_data()
    create_activation(fks)
    credential_id = fks["credential_id"]

    url = f"{api_url_v1}/activations/?credential_id={credential_id}"
    response = client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1

    url = f"{api_url_v1}/activations/?credential_id=31415"
    response = client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 0


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
@mock.patch("aap_eda.tasks.ruleset.deactivate.delay")
def test_delete_activation(delete_mock: mock.Mock, client: APIClient):
    fks = create_activation_related_data()
    activation = create_activation(fks)

    response = client.delete(f"{api_url_v1}/activations/{activation.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.ruleset.restart.delay")
def test_restart_activation(restart_mock: mock.Mock, client: APIClient):
    fks = create_activation_related_data()
    activation = create_activation(fks)

    response = client.post(
        f"{api_url_v1}/activations/{activation.id}/restart/"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["restart", "enable"])
def test_restart_activation_with_invalid_tokens(client: APIClient, action):
    fks = create_activation_related_data()
    activation = create_activation(fks)
    if action == "enable":
        activation.is_enabled = False
        activation.save(update_fields=["is_enabled"])

    models.AwxToken.objects.create(
        name="new_token_name",
        token="new_token",
        user_id=fks["user_id"],
    )

    response = client.post(
        f"{api_url_v1}/activations/{activation.id}/{action}/"
    )

    error_message = (
        "{'field_errors': 'More than one controller token found, "
        "currently only 1 token is supported'}"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["errors"] == error_message

    activation.refresh_from_db()
    assert activation.status == ActivationStatus.ERROR
    assert activation.status_message == error_message

    models.AwxToken.objects.filter(user_id=fks["user_id"]).delete()

    response = client.post(
        f"{api_url_v1}/activations/{activation.id}/{action}/"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["errors"]
        == "{'field_errors': 'No controller token specified'}"
    )
    activation.refresh_from_db()
    assert activation.status == ActivationStatus.ERROR
    assert (
        activation.status_message
        == "{'field_errors': 'No controller token specified'}"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["restart", "enable"])
def test_restart_activation_without_de(client: APIClient, action):
    fks = create_activation_related_data()
    activation = create_activation(fks)
    if action == "enable":
        activation.is_enabled = False
        activation.save(update_fields=["is_enabled"])

    models.DecisionEnvironment.objects.filter(
        id=fks["decision_environment_id"]
    ).delete()
    response = client.post(
        f"{api_url_v1}/activations/{activation.id}/{action}/"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["errors"]
        == "{'decision_environment_id': 'This field may not be null.'}"
    )
    activation.refresh_from_db()
    assert activation.status == ActivationStatus.ERROR
    assert (
        activation.status_message
        == "{'decision_environment_id': 'This field may not be null.'}"
    )


@pytest.mark.django_db
def test_enable_activation(client: APIClient):
    fks = create_activation_related_data()
    activation = create_activation(fks)

    for state in [
        ActivationStatus.STARTING,
        ActivationStatus.STOPPING,
        ActivationStatus.DELETING,
        ActivationStatus.RUNNING,
        ActivationStatus.UNRESPONSIVE,
    ]:
        activation.is_enabled = False
        activation.status = state
        activation.save(update_fields=["is_enabled", "status"])

        response = client.post(
            f"{api_url_v1}/activations/{activation.id}/enable/"
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert (
            activation.status_message
            == ACTIVATION_STATUS_MESSAGE_MAP[activation.status]
        )

    for state in [
        ActivationStatus.COMPLETED,
        ActivationStatus.PENDING,
        ActivationStatus.STOPPED,
        ActivationStatus.FAILED,
    ]:
        activation.is_enabled = False
        activation.status = state
        activation.save(update_fields=["is_enabled", "status"])

        response = client.post(
            f"{api_url_v1}/activations/{activation.id}/enable/"
        )

        activation.refresh_from_db()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert (
            activation.status_message
            == ACTIVATION_STATUS_MESSAGE_MAP[activation.status]
        )


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
                git_hash=PROJECT_GIT_HASH,
            ),
            models.ActivationInstance(
                name="test-activation-instance-1",
                activation=activation,
                git_hash=PROJECT_GIT_HASH,
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
    assert (
        data[0]["git_hash"] == instances[0].git_hash == instances[1].git_hash
    )


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
    rules_count, rules_fired_count = get_rules_count(activation.ruleset_stats)
    assert data["id"] == activation.id
    assert data["name"] == activation.name
    assert data["description"] == activation.description
    assert data["is_enabled"] == activation.is_enabled
    assert data["restart_policy"] == activation.restart_policy
    assert data["restart_count"] == activation.restart_count
    assert data["rulebook_name"] == activation.rulebook_name
    assert data["rules_count"] == rules_count
    assert data["rules_fired_count"] == rules_fired_count
    assert data["created_at"] == activation.created_at
    assert data["modified_at"] == activation.modified_at
    assert data["status_message"] == activation.status_message


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


def test_get_rules_count():
    ruleset_stats = {
        "Basic short": {
            "end": "2023-10-05T21:27:16.045381451Z",
            "start": "2023-10-05T21:27:10.656365198Z",
            "ruleSetName": "Basic short",
            "eventsMatched": 1,
            "lastClockTime": "2023-10-05T21:27:15.957Z",
            "lastRuleFired": "Run JT at 8",
            "numberOfRules": 1,
            "asyncResponses": 0,
            "rulesTriggered": 1,
            "eventsProcessed": 10,
            "lastRuleFiredAt": "2023-10-05T21:27:14.957Z",
        }
    }

    rules_count, rules_fired_count = get_rules_count(ruleset_stats)
    assert rules_count == 1
    assert rules_fired_count == 1

    stats = {
        "Basic short": {
            "end": "2023-10-05T21:27:16.045381451Z",
            "start": "2023-10-05T21:27:10.656365198Z",
            "ruleSetName": "Basic short",
            "eventsMatched": 1,
            "lastClockTime": "2023-10-05T21:27:15.957Z",
            "lastRuleFired": "Run JT at 8",
            "asyncResponses": 0,
        }
    }

    rules_count, rules_fired_count = get_rules_count(stats)
    assert rules_count == 0
    assert rules_fired_count == 0


@pytest.mark.django_db
def test_is_activation_valid():
    fks = create_activation_related_data()
    activation = create_activation(fks)

    valid, error = is_activation_valid(activation)

    assert valid is True
    assert error == "{}"  # noqa P103


@pytest.mark.django_db
def test_create_activation_no_token(client: APIClient):
    fks = create_activation_related_data()
    test_activation = TEST_ACTIVATION.copy()
    test_activation["is_enabled"] = True
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["extra_var_id"] = fks["extra_var_id"]

    response = client.post(f"{api_url_v1}/activations/", data=test_activation)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        str(response.data["errors"])
        == "{'field_errors': 'No controller token specified'}"
    )


@pytest.mark.django_db
def test_create_activation_more_tokens(client: APIClient):
    fks = create_activation_related_data()
    test_activation = TEST_ACTIVATION.copy()
    test_activation["is_enabled"] = True
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["extra_var_id"] = fks["extra_var_id"]

    client.post(f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN)
    client.post(f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN_2)
    response = client.post(f"{api_url_v1}/activations/", data=test_activation)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        str(response.data["errors"])
        == "{'field_errors': 'More than one controller token found, "
        "currently only 1 token is supported'}"
    )
