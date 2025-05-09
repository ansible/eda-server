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
import re
from typing import Any, Dict, List
from unittest import mock
from unittest.mock import patch

import pytest
import redis
import yaml
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.api.serializers.activation import (
    get_rules_count,
    is_activation_valid,
)
from aap_eda.api.serializers.project import ENCRYPTED_STRING
from aap_eda.core import enums, models
from tests.integration.constants import api_url_v1

PROJECT_GIT_HASH = "684f62df18ce5f8d5c428e53203b9b975426eed0"


def converted_extra_var(var: str) -> str:
    return yaml.safe_dump(yaml.safe_load(var))


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
def test_create_activation(
    admin_awx_token: models.AwxToken,
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_info: dict,
    admin_client: APIClient,
):
    response = admin_client.post(
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
    assert data["extra_var"] == converted_extra_var(
        activation_payload["extra_var"]
    )
    assert activation.rulebook_name == default_rulebook.name
    assert activation.rulebook_rulesets == default_rulebook.rulesets
    assert data["restarted_at"] is None
    assert activation.status == enums.ActivationStatus.PENDING
    assert activation.status_message == (
        "Wait for a worker to be available to start activation"
    )
    assert activation.created_by.username == admin_info["username"]
    assert activation.modified_by.username == admin_info["username"]
    assert not activation.skip_audit_events


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
def test_create_activation_blank_text(
    admin_awx_token: models.AwxToken,
    activation_payload_blank_text: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
):
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload_blank_text
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.data
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert_activation_base_data(
        data,
        activation,
    )
    assert data["description"] == activation_payload_blank_text["description"]

    # An extra_var empty string is outbound serialized as None; it's considered
    # a "no value" situation.  Consequently, a data content of None for
    # extra_var may be sourced from either None or an empty string.
    if activation_payload_blank_text["extra_var"] == "":
        assert data["extra_var"] is None
    else:
        assert data["extra_var"] == activation_payload_blank_text["extra_var"]

    assert (
        data["k8s_service_name"]
        == activation_payload_blank_text["k8s_service_name"]
    )
    assert data["log_level"] == activation_payload_blank_text["log_level"]
    assert data["project"]["id"] == activation_payload_blank_text["project_id"]
    assert (
        data["rulebook"]["id"] == activation_payload_blank_text["rulebook_id"]
    )
    assert (
        data["decision_environment"]["id"]
        == activation_payload_blank_text["decision_environment_id"]
    )
    assert activation.rulebook_name == default_rulebook.name
    assert activation.rulebook_rulesets == default_rulebook.rulesets
    assert data["restarted_at"] is None
    assert activation.status == enums.ActivationStatus.PENDING
    assert activation.status_message == (
        "Wait for a worker to be available to start activation"
    )


@pytest.mark.django_db
def test_create_activation_disabled(
    activation_payload: Dict[str, Any],
    admin_awx_token: models.AwxToken,
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
):
    activation_payload["is_enabled"] = False
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = admin_client.get(
        f"{api_url_v1}/activations/{response.data['id']}/"
    )
    data = response.data
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert activation.rulebook_name == default_rulebook.name
    assert activation.rulebook_rulesets == default_rulebook.rulesets
    assert activation.status == enums.ActivationStatus.PENDING
    assert activation.status_message == "Activation is marked as disabled"
    assert not data["instances"]


@pytest.mark.django_db
def test_create_activation_bad_entity(admin_client: APIClient):
    test_activation = {
        "name": "test-activation",
        "description": "test activation",
        "is_enabled": True,
    }
    response = admin_client.post(
        f"{api_url_v1}/activations/",
        data=test_activation,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.parametrize(
    "enabled",
    [True, False],
)
@pytest.mark.django_db
@mock.patch("aap_eda.core.tasking.is_redis_failed", return_value=True)
def test_create_activation_redis_unavailable(
    is_redis_failed: mock.Mock,
    activation_payload: Dict[str, Any],
    admin_awx_token: models.AwxToken,
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    enabled: bool,
    preseed_credential_types,
):
    activation_payload["is_enabled"] = enabled
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )

    if not enabled:
        assert response.status_code == status.HTTP_201_CREATED
    else:
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {
            "detail": "Redis is required but unavailable."
        }


@pytest.mark.parametrize(
    "dependent_object",
    [
        {
            "decision_environment": "DecisionEnvironment with id 0 does not exist"  # noqa: E501
        },
        {"rulebook": "Rulebook with id 0 does not exist"},
    ],
)
@pytest.mark.django_db
def test_create_activation_with_bad_entity(
    activation_payload: Dict[str, Any],
    admin_awx_token: models.AwxToken,
    admin_client: APIClient,
    dependent_object: str,
    preseed_credential_types,
):
    for key in dependent_object:
        response = admin_client.post(
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


NOT_OBJECT_ERROR_MSG = "Extra var is not in object format"
NOT_YAML_JSON_ERROR_MSG = "Extra var must be in JSON or YAML format"


@pytest.mark.parametrize(
    "extra_var,error_message",
    [
        ("John", NOT_OBJECT_ERROR_MSG),
        ("John, ", NOT_OBJECT_ERROR_MSG),
        ("[John, 3,]", NOT_OBJECT_ERROR_MSG),
        ('{"name": "John" - 2 }', NOT_YAML_JSON_ERROR_MSG),
        (
            '{"eda": "Fred"}',
            (
                "Extra vars key 'eda' cannot be one of these reserved keys "
                "'ansible, eda'"
            ),
        ),
        (
            '{"ansible": "Fred"}',
            (
                "Extra vars key 'ansible' cannot be one of these reserved "
                "keys 'ansible, eda'"
            ),
        ),
    ],
)
@pytest.mark.django_db
def test_create_activation_with_bad_extra_var(
    activation_payload: Dict[str, Any],
    admin_awx_token: models.AwxToken,
    admin_client: APIClient,
    preseed_credential_types,
    extra_var: str,
    error_message: str,
):
    response = admin_client.post(
        f"{api_url_v1}/activations/",
        data={
            **activation_payload,
            "extra_var": extra_var,
        },
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert str(response.data["extra_var"][0]) == error_message


@pytest.mark.parametrize(
    "extra_var",
    [
        "John: Doe",
        "John: 2",
        '{"name": "John"}',
        '"age": 20',
        "---\nname: hello\nhosts: localhost\ngather_facts: false",
    ],
)
@pytest.mark.django_db
def test_create_activation_with_valid_extra_var(
    activation_payload: Dict[str, Any],
    admin_awx_token: models.AwxToken,
    admin_client: APIClient,
    preseed_credential_types,
    extra_var: str,
):
    response = admin_client.post(
        f"{api_url_v1}/activations/",
        data={
            **activation_payload,
            "extra_var": extra_var,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_create_activation_with_vault_extra_var(
    activation_payload: Dict[str, Any],
    admin_awx_token: models.AwxToken,
    admin_client: APIClient,
    preseed_credential_types,
    vault_extra_var_data: str,
):
    response = admin_client.post(
        f"{api_url_v1}/activations/",
        data={
            **activation_payload,
            "extra_var": vault_extra_var_data,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    id = response.data["id"]
    assert response.data["extra_var"] == f"limit: {ENCRYPTED_STRING}\n"
    assert models.Activation.objects.filter(pk=id).exists()
    assert models.Activation.objects.first().extra_var == vault_extra_var_data


@pytest.mark.django_db
def test_create_activation_with_null_credentials(
    activation_payload: Dict[str, Any],
    admin_awx_token: models.AwxToken,
    admin_client: APIClient,
    preseed_credential_types,
):
    response = admin_client.post(
        f"{api_url_v1}/activations/",
        data={
            **activation_payload,
            "eda_credentials": None,
        },
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        str(response.data["eda_credentials"][0])
        == "This field may not be null."
    )


@pytest.mark.django_db
def test_list_activations(
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    activations = [default_activation]
    response = admin_client.get(f"{api_url_v1}/activations/")
    assert response.status_code == status.HTTP_200_OK
    for data, activation in zip(response.data["results"], activations):
        assert_activation_base_data(data, activation)
        assert_activation_related_object_fks(data, activation)


@pytest.mark.django_db
def test_list_activations_filter_name(
    default_activation: models.Activation,
    new_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    filter_name = "new"
    activations = [default_activation, new_activation]

    response = admin_client.get(
        f"{api_url_v1}/activations/?name={filter_name}"
    )
    assert response.status_code == status.HTTP_200_OK
    response_data = response.data["results"]
    assert len(response_data) == 1
    assert_activation_base_data(response_data[0], activations[1])


@pytest.mark.django_db
def test_list_activations_filter_name_none_exist(
    default_activation: models.Activation,
    new_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    filter_name = "noname"

    response = admin_client.get(
        f"{api_url_v1}/activations/?name={filter_name}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["results"] == []


@pytest.mark.django_db
def test_list_activations_filter_status(
    default_activation: models.Activation,
    new_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    filter_status = enums.ActivationStatus.FAILED
    new_activation.status = enums.ActivationStatus.FAILED
    new_activation.save(update_fields=["status"])
    activations = [default_activation, new_activation]

    response = admin_client.get(
        f"{api_url_v1}/activations/?status={filter_status}"
    )
    assert response.status_code == status.HTTP_200_OK
    response_data = response.data["results"]
    assert_activation_base_data(response_data[0], activations[1])


@pytest.mark.django_db
def test_list_activations_filter_decision_environment_id(
    default_activation: models.Activation,
    new_activation: models.Activation,
    default_decision_environment: models.DecisionEnvironment,
    admin_client: APIClient,
    preseed_credential_types,
):
    activations = [default_activation, new_activation]
    de_id = default_decision_environment.id

    response = admin_client.get(
        f"{api_url_v1}/activations/?decision_environment_id={de_id}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == len(activations)

    response = admin_client.get(
        f"{api_url_v1}/activations/?decision_environment_id=0"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 0


@pytest.mark.django_db
def test_retrieve_activation(
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    response = admin_client.get(
        f"{api_url_v1}/activations/{default_activation.id}/"
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.data
    assert_activation_base_data(data, default_activation)
    assert data["ruleset_stats"] == ""
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
def test_retrieve_activation_with_ruleset_stats(
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    stats = {
        "ruleset": {
            "start": "2024-08-21T17:03:01.577285Z",
            "end": None,
            "numberOfRules": 1,
            "numberOfDisabledRules": 0,
            "rulesTriggered": 1,
            "eventsProcessed": 2000,
            "eventsMatched": 1,
            "eventsSuppressed": 1999,
            "permanentStorageSize": 0,
            "asyncResponses": 0,
            "bytesSentOnAsync": 0,
            "sessionId": 1,
            "ruleSetName": "ruleset",
        }
    }

    default_activation.ruleset_stats = stats
    default_activation.save(update_fields=["ruleset_stats"])

    response = admin_client.get(
        f"{api_url_v1}/activations/{default_activation.id}/"
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.data
    assert_activation_base_data(data, default_activation)
    assert yaml.safe_load(response.data["ruleset_stats"]) == stats


@pytest.mark.django_db
def test_retrieve_activation_not_exist(admin_client: APIClient):
    response = admin_client.get(f"{api_url_v1}/activations/77/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("activation_status", "expected_response"),
    [
        (
            enums.ActivationStatus.PENDING,
            status.HTTP_204_NO_CONTENT,
        ),
        (
            enums.ActivationStatus.WORKERS_OFFLINE,
            status.HTTP_409_CONFLICT,
        ),
    ],
)
def test_delete_activation(
    activation_status: enums.ActivationStatus,
    expected_response: int,
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    default_activation.status = activation_status
    default_activation.save(update_fields=["status"])

    response = admin_client.delete(
        f"{api_url_v1}/activations/{default_activation.id}/"
    )
    assert response.status_code == expected_response


@pytest.mark.django_db
@mock.patch("aap_eda.core.tasking.is_redis_failed", return_value=True)
@mock.patch("aap_eda.api.views.activation.delete_rulebook_process")
def test_delete_activation_redis_unavailable(
    delete_rule_book_process: mock.Mock,
    is_redis_failed: mock.Mock,
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    def raise_connection_error(*args, **kwargs):
        raise redis.ConnectionError("redis unavailable")

    delete_rule_book_process.side_effect = raise_connection_error

    response = admin_client.delete(
        f"{api_url_v1}/activations/{default_activation.id}/"
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "Redis is required but unavailable."}


@pytest.mark.django_db
def test_restart_activation(
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    response = admin_client.post(
        f"{api_url_v1}/activations/{default_activation.id}/restart/"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("force_restart", "expected_response"),
    [
        (
            "true",
            status.HTTP_204_NO_CONTENT,
        ),
        (
            "false",
            status.HTTP_409_CONFLICT,
        ),
    ],
)
@patch("aap_eda.api.serializers.activation.settings.DEPLOYMENT_TYPE", "podman")
def test_restart_activation_workers_offline(
    force_restart,
    expected_response,
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    default_activation.status = enums.ActivationStatus.WORKERS_OFFLINE
    default_activation.save(update_fields=["status"])

    response = admin_client.post(
        f"{api_url_v1}/activations/{default_activation.id}/restart/"
        f"?force={force_restart}"
    )
    assert response.status_code == expected_response


@pytest.mark.parametrize(
    ("missing_field", "error_message"),
    [
        (
            "decision_environment_id",
            "Decision Environment is required",
        ),
        (
            "organization_id",
            "Organization is required",
        ),
        (
            "rulebook_id",
            "Rulebook is required",
        ),
    ],
)
@pytest.mark.django_db
def test_create_activation_with_missing_required_fields(
    activation_payload: Dict[str, Any],
    admin_client: APIClient,
    missing_field,
    error_message,
    preseed_credential_types,
):
    activation_payload.pop(missing_field)
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert error_message in response.data[missing_field]


@pytest.mark.parametrize(
    "enabled",
    [True, False],
)
@pytest.mark.django_db
@mock.patch("aap_eda.core.tasking.is_redis_failed", return_value=True)
def test_restart_activation_redis_unavailable(
    is_redis_failed: mock.Mock,
    default_activation: models.Activation,
    admin_client: APIClient,
    enabled: bool,
    preseed_credential_types,
):
    default_activation.is_enabled = enabled
    default_activation.save(update_fields=["is_enabled"])

    response = admin_client.post(
        f"{api_url_v1}/activations/{default_activation.id}/restart/"
    )

    if not enabled:
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {
            "detail": "Activation is disabled and cannot be run."
        }
    else:
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {
            "detail": "Redis is required but unavailable."
        }


@pytest.mark.django_db
@pytest.mark.parametrize("action", [enums.Action.RESTART, enums.Action.ENABLE])
def test_restart_activation_without_de(
    default_activation: models.Activation,
    default_decision_environment: models.DecisionEnvironment,
    admin_client: APIClient,
    action,
    preseed_credential_types,
):
    if action == enums.Action.ENABLE:
        default_activation.is_enabled = False
        default_activation.save(update_fields=["is_enabled"])

    models.DecisionEnvironment.objects.filter(
        id=default_decision_environment.id
    ).delete()
    response = admin_client.post(
        f"{api_url_v1}/activations/{default_activation.id}/{action}/"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["errors"]
        == "{'decision_environment_id': 'Decision Environment is needed'}"
    )
    default_activation.refresh_from_db()
    assert default_activation.status == enums.ActivationStatus.ERROR
    assert (
        default_activation.status_message
        == "{'decision_environment_id': 'Decision Environment is needed'}"
    )


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
def test_enable_activation(
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
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

        response = admin_client.post(
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

        response = admin_client.post(
            f"{api_url_v1}/activations/{default_activation.id}/enable/"
        )

        default_activation.refresh_from_db()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert default_activation.status_message == (
            "Wait for a worker to be available to start activation"
        )


@pytest.mark.parametrize(
    "enabled",
    [True, False],
)
@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@mock.patch("aap_eda.core.tasking.is_redis_failed", return_value=True)
def test_enable_activation_redis_unavailable(
    is_redis_failed: mock.Mock,
    default_activation: models.Activation,
    admin_client: APIClient,
    enabled: bool,
    preseed_credential_types,
):
    default_activation.is_enabled = enabled
    default_activation.save(update_fields=["is_enabled"])

    response = admin_client.post(
        f"{api_url_v1}/activations/{default_activation.id}/enable/"
    )

    if enabled:
        assert response.status_code == status.HTTP_204_NO_CONTENT
    else:
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {
            "detail": "Redis is required but unavailable."
        }


@pytest.mark.django_db
def test_disable_activation(
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    response = admin_client.post(
        f"{api_url_v1}/activations/{default_activation.id}/disable/"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.parametrize(
    "enabled",
    [True, False],
)
@pytest.mark.django_db
@mock.patch("aap_eda.core.tasking.is_redis_failed", return_value=True)
def test_disable_activation_redis_unavailable(
    is_redis_failed: mock.Mock,
    default_activation: models.Activation,
    admin_client: APIClient,
    enabled: bool,
    preseed_credential_types,
):
    default_activation.is_enabled = enabled
    default_activation.save(update_fields=["is_enabled"])

    response = admin_client.post(
        f"{api_url_v1}/activations/{default_activation.id}/disable/"
    )

    if not enabled:
        assert response.status_code == status.HTTP_204_NO_CONTENT
    else:
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {
            "detail": "Redis is required but unavailable."
        }


@pytest.mark.django_db
def test_list_activation_instances(
    default_activation: models.Activation,
    default_activation_instances: List[models.RulebookProcess],
    admin_client: APIClient,
    preseed_credential_types,
):
    instances = sorted(
        default_activation_instances, key=lambda x: x.started_at
    )
    response = admin_client.get(
        f"{api_url_v1}/activations/{default_activation.id}/instances/"
    )
    data = sorted(response.data["results"], key=lambda x: x["started_at"])
    assert response.status_code == status.HTTP_200_OK
    assert len(data) == len(instances)
    assert data[0]["name"] == instances[0].name
    assert data[1]["name"] == instances[1].name
    assert (
        data[0]["git_hash"] == instances[0].git_hash == instances[1].git_hash
    )


@pytest.mark.django_db
def test_list_activation_instances_filter_name(
    default_activation: models.Activation,
    default_activation_instances: List[models.RulebookProcess],
    admin_client: APIClient,
    preseed_credential_types,
):
    instances = default_activation_instances

    filter_name = "instance-1"
    response = admin_client.get(
        f"{api_url_v1}/activations/{default_activation.id}"
        f"/instances/?name={filter_name}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["name"] == instances[0].name


@pytest.mark.django_db
def test_list_activation_instances_filter_status(
    default_activation: models.Activation,
    default_activation_instances: List[models.RulebookProcess],
    admin_client: APIClient,
    preseed_credential_types,
):
    instances = default_activation_instances

    filter_status = enums.ActivationStatus.FAILED
    response = admin_client.get(
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

    # An extra_var empty string is outbound serialized as None; it's considered
    # a "no value" situation.  Consequently, a data content of None for
    # extra_var may be sourced from either None or an empty string.
    if (activation.extra_var is None) or (activation.extra_var == ""):
        assert data["extra_var"] is None
    else:
        assert data["extra_var"] == converted_extra_var(activation.extra_var)

    assert data["restart_policy"] == activation.restart_policy
    assert data["restart_count"] == activation.restart_count
    assert data["rulebook_name"] == activation.rulebook_name
    assert data["rules_count"] == rules_count
    assert data["rules_fired_count"] == rules_fired_count
    assert data["created_at"] == activation.created_at
    assert data["modified_at"] <= activation.modified_at
    assert data["status_message"]


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
def test_is_activation_valid(
    default_activation: models.Activation, preseed_credential_types
):
    valid, error = is_activation_valid(default_activation)

    assert valid is True
    assert error == "{}"  # noqa P103


@pytest.mark.django_db
def test_create_activation_no_token_no_required(
    activation_payload, admin_client: APIClient, preseed_credential_types
):
    """Test that an activation can be created without a token if the
    rulebook does not require one."""
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_create_activation_no_token_but_required(
    admin_client: APIClient,
    rulebook_with_job_template: models.Rulebook,
    activation_payload: Dict[str, Any],
    preseed_credential_types,
):
    """Test that an activation cannot be created without a token if the
    rulebook requires one."""
    activation_payload["rulebook_id"] = rulebook_with_job_template.id

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "The rulebook requires a RH AAP credential."
        in response.data["non_field_errors"]
    )


@pytest.mark.django_db
def test_create_activation_with_invalid_token(
    admin_client: APIClient,
    rulebook_with_job_template: models.Rulebook,
    default_user_awx_token: models.AwxToken,
    activation_payload: Dict[str, Any],
    preseed_credential_types,
):
    """Test that an activation cannot be created with a token that
    does not belong to the user."""
    activation_payload["rulebook_id"] = rulebook_with_job_template.id
    activation_payload["awx_token_id"] = default_user_awx_token.id

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "The Awx Token does not belong to the user."
        in response.data["non_field_errors"]
    )


class IsUUID:
    pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"  # noqa: E501

    def __eq__(self, other):
        return re.match(self.pattern, other, re.IGNORECASE) is not None


@pytest.mark.django_db
def test_restart_activation_with_required_token_deleted(
    admin_client: APIClient,
    rulebook_with_job_template: models.Rulebook,
    admin_awx_token: models.AwxToken,
    activation_payload: Dict[str, Any],
    preseed_credential_types,
):
    """Test that an activation cannot be restarted when the token
    required is deleted."""
    activation_payload["rulebook_id"] = rulebook_with_job_template.id
    activation_payload["awx_token_id"] = admin_awx_token.id
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    token = models.AwxToken.objects.get(id=admin_awx_token.id)
    token.delete()
    activation_id = response.data["id"]

    with mock.patch(
        "aap_eda.api.views.activation.stop_rulebook_process"
    ) as mock_stop:
        response = admin_client.post(
            f"{api_url_v1}/activations/{activation_id}/restart/",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            "The rulebook requires a RH AAP credential."
            in response.data["errors"]
        )
        mock_stop.assert_called_once_with(
            process_parent_type=enums.ProcessParentType.ACTIVATION,
            process_parent_id=activation_id,
            request_id=IsUUID(),
        )


@pytest.mark.django_db
def test_create_activation_with_awx_token(
    admin_client: APIClient,
    rulebook_with_job_template: models.Rulebook,
    admin_awx_token: models.AwxToken,
    activation_payload: Dict[str, Any],
    preseed_credential_types,
):
    """Test that an activation can be created with a token if the
    rulebook requires one."""
    activation_payload["rulebook_id"] = rulebook_with_job_template.id
    activation_payload["awx_token_id"] = admin_awx_token.id

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
def test_create_activation_with_skip_audit_events(
    admin_awx_token: models.AwxToken,
    activation_payload_skip_audit_events: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
):
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload_skip_audit_events
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.data
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert activation.skip_audit_events


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
def test_activation_by_fields(
    activation_payload: Dict[str, Any],
    admin_user: models.User,
    super_user: models.User,
    base_client: APIClient,
):
    base_client.force_authenticate(user=admin_user)
    response = base_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.data

    assert data["created_by"]["username"] == admin_user.username
    assert data["modified_by"]["username"] == admin_user.username

    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert activation.created_by == admin_user
    assert activation.modified_by == admin_user

    response = base_client.get(f"{api_url_v1}/activations/{activation.id}/")
    assert response.status_code == status.HTTP_200_OK
    data = response.data

    assert data["created_by"]["username"] == admin_user.username
    assert data["modified_by"]["username"] == admin_user.username


@pytest.mark.django_db
@patch("aap_eda.api.serializers.activation.settings.DEPLOYMENT_TYPE", "k8s")
def test_update_activation(
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
):
    activation_payload["is_enabled"] = False
    activation_payload["k8s_service_name"] = "myservice"
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED

    id = response.data["id"]
    updated_data = {
        "description": "another_name",
        "is_enabled": True,
        "k8s_service_name": "",
    }
    response = admin_client.patch(
        f"{api_url_v1}/activations/{id}/",
        data=updated_data,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.data
    assert data["edited_at"] is not None
    assert data["edited_by"]["username"] == "test.admin"
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert activation.description == "another_name"
    assert activation.edited_at is not None
    assert activation.edited_by.username == "test.admin"
    assert activation.k8s_service_name == activation.name
    assert activation.is_enabled is True
    assert activation.status == enums.ActivationStatus.PENDING


@pytest.mark.django_db
def test_update_activation_invalid_body(
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
):
    activation_payload["is_enabled"] = False
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED

    id = response.data["id"]
    response = admin_client.patch(
        f"{api_url_v1}/activations/{id}/", data={"rulebook_id": None}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_update_enabled_activation(
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
):
    activation_payload["is_enabled"] = True
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED

    id = response.data["id"]
    response = admin_client.patch(
        f"{api_url_v1}/activations/{id}/", data={"name": "another_name"}
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        response.data
        == "Activation is not in disabled mode and in stopped status"
    )


@pytest.mark.django_db
def test_copy_activation(
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
):
    activation_payload["is_enabled"] = True
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED

    a_id = response.data["id"]
    response = admin_client.post(
        f"{api_url_v1}/activations/{a_id}/copy/", data={"name": "another_name"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.data
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert activation.name == "another_name"
    assert activation.is_enabled is False


@pytest.mark.django_db
def test_copy_activation_invalid_body(
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
):
    activation_payload["is_enabled"] = False
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED

    a_id = response.data["id"]
    name = response.data["name"]
    response = admin_client.post(
        f"{api_url_v1}/activations/{a_id}/copy/", data={}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    response = admin_client.post(
        f"{api_url_v1}/activations/{a_id}/copy/", data={"name": name}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
