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

from aap_eda.api.serializers.activation import (
    get_rules_count,
    is_activation_valid,
)
from aap_eda.core import enums, models
from tests.integration.constants import api_url_v1

PROJECT_GIT_HASH = "684f62df18ce5f8d5c428e53203b9b975426eed0"


@pytest.mark.django_db
def test_create_activation(
    admin_awx_token: models.AwxToken,
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    client: APIClient,
):
    response = client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.data
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert_activation_base_data(
        data,
        activation,
    )
    assert data["log_level"] == activation_payload["log_level"]
    assert data["project"]["id"] == activation_payload["project_id"]
    assert data["rulebook"]["id"] == activation_payload["rulebook_id"]
    assert (
        data["decision_environment"]["id"]
        == activation_payload["decision_environment_id"]
    )
    assert data["extra_var"]["id"] == activation_payload["extra_var_id"]
    assert activation.rulebook_name == default_rulebook.name
    assert activation.rulebook_rulesets == default_rulebook.rulesets
    assert data["restarted_at"] is None
    assert activation.status == enums.ActivationStatus.PENDING
    assert (
        activation.status_message
        == enums.ACTIVATION_STATUS_MESSAGE_MAP[activation.status]
    )


@pytest.mark.django_db
def test_create_activation_disabled(
    activation_payload: Dict[str, Any],
    admin_awx_token: models.AwxToken,
    default_rulebook: models.Rulebook,
    client: APIClient,
):
    activation_payload["is_enabled"] = False
    response = client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = client.get(f"{api_url_v1}/activations/{response.data['id']}/")
    data = response.data
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert activation.rulebook_name == default_rulebook.name
    assert activation.rulebook_rulesets == default_rulebook.rulesets
    assert activation.status == enums.ActivationStatus.PENDING
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
    activation_payload: Dict[str, Any],
    admin_awx_token: models.AwxToken,
    client: APIClient,
    dependent_object: str,
):
    for key in dependent_object:
        response = client.post(
            f"{api_url_v1}/activations/",
            data={
                **activation_payload,
                f"{key}_id": 0,
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data[f"{key}_id"][0] == f"{dependent_object[key]}"

    # Since responses are 400 errors, these checks can happen before
    # permission checks, which is why check_permission_mock is not checked here


@pytest.mark.django_db
def test_list_activations(
    default_activation: models.Activation, client: APIClient
):
    activations = [default_activation]
    response = client.get(f"{api_url_v1}/activations/")
    assert response.status_code == status.HTTP_200_OK
    for data, activation in zip(response.data["results"], activations):
        assert_activation_base_data(data, activation)
        assert_activation_related_object_fks(data, activation)


@pytest.mark.django_db
def test_list_activations_filter_name(
    default_activation: models.Activation,
    new_activation: models.Activation,
    client: APIClient,
):
    filter_name = "new"
    activations = [default_activation, new_activation]

    response = client.get(f"{api_url_v1}/activations/?name={filter_name}")
    assert response.status_code == status.HTTP_200_OK
    response_data = response.data["results"]
    assert len(response_data) == 1
    assert_activation_base_data(response_data[0], activations[1])


@pytest.mark.django_db
def test_list_activations_filter_name_none_exist(
    default_activation: models.Activation,
    new_activation: models.Activation,
    client: APIClient,
):
    filter_name = "noname"

    response = client.get(f"{api_url_v1}/activations/?name={filter_name}")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["results"] == []


@pytest.mark.django_db
def test_list_activations_filter_status(
    default_activation: models.Activation,
    new_activation: models.Activation,
    client: APIClient,
):
    filter_status = enums.ActivationStatus.FAILED
    new_activation.status = enums.ActivationStatus.FAILED
    new_activation.save(update_fields=["status"])
    activations = [default_activation, new_activation]

    response = client.get(f"{api_url_v1}/activations/?status={filter_status}")
    assert response.status_code == status.HTTP_200_OK
    response_data = response.data["results"]
    assert_activation_base_data(response_data[0], activations[1])


@pytest.mark.django_db
def test_list_activations_filter_decision_environment_id(
    default_activation: models.Activation,
    new_activation: models.Activation,
    default_de: models.DecisionEnvironment,
    client: APIClient,
):
    activations = [default_activation, new_activation]
    de_id = default_de.id

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
def test_list_activations_filter_credential_id(
    default_activation: models.Activation,
    default_eda_credential: models.EdaCredential,
    client: APIClient,
) -> None:
    """Test filtering by credential_id."""

    url = (
        f"{api_url_v1}/activations/?credential_id={default_eda_credential.id}"
    )
    response = client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1

    url = f"{api_url_v1}/activations/?credential_id=31415"
    response = client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 0


@pytest.mark.django_db
def test_retrieve_activation(
    default_activation: models.Activation, client: APIClient
):
    response = client.get(f"{api_url_v1}/activations/{default_activation.id}/")
    assert response.status_code == status.HTTP_200_OK
    data = response.data
    assert_activation_base_data(data, default_activation)
    if default_activation.project:
        assert data["project"]["id"] == default_activation.project.id
    else:
        assert not data["project"]
    if default_activation.rulebook:
        assert data["rulebook"]["id"] == default_activation.rulebook.id
    else:
        assert not data["rulebook"]
    assert (
        data["decision_environment"]["id"]
        == default_activation.decision_environment.id
    )
    assert data["extra_var"]["id"] == default_activation.extra_var.id
    activation_instances = models.RulebookProcess.objects.filter(
        activation_id=default_activation.id
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
def test_delete_activation(
    default_activation: models.Activation, client: APIClient
):
    response = client.delete(
        f"{api_url_v1}/activations/{default_activation.id}/"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_restart_activation(
    default_activation: models.Activation, client: APIClient
):
    response = client.post(
        f"{api_url_v1}/activations/{default_activation.id}/restart/"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["restart", "enable"])
def test_restart_activation_without_de(
    default_activation: models.Activation,
    default_de: models.DecisionEnvironment,
    client: APIClient,
    action,
):
    if action == enums.Action.ENABLE:
        default_activation.is_enabled = False
        default_activation.save(update_fields=["is_enabled"])

    models.DecisionEnvironment.objects.filter(id=default_de.id).delete()
    response = client.post(
        f"{api_url_v1}/activations/{default_activation.id}/{action}/"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["errors"]
        == "{'decision_environment_id': 'This field may not be null.'}"
    )
    default_activation.refresh_from_db()
    assert default_activation.status == enums.ActivationStatus.ERROR
    assert (
        default_activation.status_message
        == "{'decision_environment_id': 'This field may not be null.'}"
    )


@pytest.mark.django_db
def test_enable_activation(
    default_activation: models.Activation, client: APIClient
):
    for state in [
        enums.ActivationStatus.STARTING,
        enums.ActivationStatus.STOPPING,
        enums.ActivationStatus.DELETING,
        enums.ActivationStatus.RUNNING,
        enums.ActivationStatus.UNRESPONSIVE,
    ]:
        default_activation.is_enabled = False
        default_activation.status = state
        default_activation.save(update_fields=["is_enabled", "status"])

        response = client.post(
            f"{api_url_v1}/activations/{default_activation.id}/enable/"
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert (
            default_activation.status_message
            == enums.ACTIVATION_STATUS_MESSAGE_MAP[default_activation.status]
        )

    for state in [
        enums.ActivationStatus.COMPLETED,
        enums.ActivationStatus.PENDING,
        enums.ActivationStatus.STOPPED,
        enums.ActivationStatus.FAILED,
    ]:
        default_activation.is_enabled = False
        default_activation.status = state
        default_activation.save(update_fields=["is_enabled", "status"])

        response = client.post(
            f"{api_url_v1}/activations/{default_activation.id}/enable/"
        )

        default_activation.refresh_from_db()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert (
            default_activation.status_message
            == enums.ACTIVATION_STATUS_MESSAGE_MAP[default_activation.status]
        )


@pytest.mark.django_db
def test_disable_activation(
    default_activation: models.Activation, client: APIClient
):
    response = client.post(
        f"{api_url_v1}/activations/{default_activation.id}/disable/"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_list_activation_instances(
    default_activation: models.Activation, client: APIClient
):
    instances = models.RulebookProcess.objects.bulk_create(
        [
            models.RulebookProcess(
                name="test-activation-instance-1",
                activation=default_activation,
                git_hash=PROJECT_GIT_HASH,
            ),
            models.RulebookProcess(
                name="test-activation-instance-1",
                activation=default_activation,
                git_hash=PROJECT_GIT_HASH,
            ),
        ]
    )
    response = client.get(
        f"{api_url_v1}/activations/{default_activation.id}/instances/"
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
def test_list_activation_instances_filter_name(
    default_activation: models.Activation, client: APIClient
):
    instances = models.RulebookProcess.objects.bulk_create(
        [
            models.RulebookProcess(
                name="activation-instance-1",
                activation=default_activation,
            ),
            models.RulebookProcess(
                name="test-activation-instance-2",
                activation=default_activation,
            ),
        ]
    )

    filter_name = "instance-1"
    response = client.get(
        f"{api_url_v1}/activations/{default_activation.id}"
        f"/instances/?name={filter_name}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["name"] == instances[0].name


@pytest.mark.django_db
def test_list_activation_instances_filter_status(
    default_activation: models.Activation, client: APIClient
):
    instances = models.RulebookProcess.objects.bulk_create(
        [
            models.RulebookProcess(
                name="activation-instance-1",
                status="completed",
                activation=default_activation,
            ),
            models.RulebookProcess(
                name="test-activation-instance-2",
                status="failed",
                activation=default_activation,
            ),
        ]
    )

    filter_status = enums.ActivationStatus.FAILED
    response = client.get(
        f"{api_url_v1}/activations/{default_activation.id}"
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
    assert data["organization_id"] == activation.organization.id


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
def test_is_activation_valid(default_activation: models.Activation):
    valid, error = is_activation_valid(default_activation)

    assert valid is True
    assert error == "{}"  # noqa P103


@pytest.mark.django_db
def test_create_activation_no_token_no_required(
    activation_payload, client: APIClient
):
    """Test that an activation can be created without a token if the
    rulebook does not require one."""
    response = client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_create_activation_no_token_but_required(
    client: APIClient,
    rulebook_with_job_template: models.Rulebook,
    activation_payload: Dict[str, Any],
):
    """Test that an activation cannot be created without a token if the
    rulebook requires one."""
    activation_payload["rulebook_id"] = rulebook_with_job_template.id

    response = client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "The rulebook requires an Awx Token."
        in response.data["non_field_errors"]
    )


@pytest.mark.django_db
def test_create_activation_with_invalid_token(
    client: APIClient,
    rulebook_with_job_template: models.Rulebook,
    default_user_awx_token: models.AwxToken,
    activation_payload: Dict[str, Any],
):
    """Test that an activation cannot be created with a token that
    does not belong to the user."""
    activation_payload["rulebook_id"] = rulebook_with_job_template.id
    activation_payload["awx_token_id"] = default_user_awx_token.id

    response = client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "The Awx Token does not belong to the user."
        in response.data["non_field_errors"]
    )


@pytest.mark.django_db
def test_restart_activation_with_required_token_deleted(
    client: APIClient,
    rulebook_with_job_template: models.Rulebook,
    admin_awx_token: models.AwxToken,
    activation_payload: Dict[str, Any],
):
    """Test that an activation cannot be restarted when the token
    required is deleted."""
    activation_payload["rulebook_id"] = rulebook_with_job_template.id
    activation_payload["awx_token_id"] = admin_awx_token.id
    response = client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    token = models.AwxToken.objects.get(id=admin_awx_token.id)
    token.delete()

    response = client.post(
        f"{api_url_v1}/activations/{response.data['id']}/restart/",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "The rulebook requires an Awx Token." in response.data["errors"]


@pytest.mark.django_db
def test_create_activation_with_awx_token(
    client: APIClient,
    rulebook_with_job_template: models.Rulebook,
    admin_awx_token: models.AwxToken,
    activation_payload: Dict[str, Any],
):
    """Test that an activation can be created with a token if the
    rulebook requires one."""
    activation_payload["rulebook_id"] = rulebook_with_job_template.id
    activation_payload["awx_token_id"] = admin_awx_token.id

    response = client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
