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
from aap_eda.core.utils.rulebook import get_rulebook_hash
from tests.integration.constants import api_url_v1

PROJECT_GIT_HASH = "684f62df18ce5f8d5c428e53203b9b975426eed0"


def converted_extra_var(var: str) -> str:
    return yaml.safe_dump(yaml.safe_load(var))


def ensure_default_rule_engine_credential(
    organization: models.Organization,
) -> models.EdaCredential:
    """Create the default rule engine credential if it doesn't exist.

    This helper ensures the default system credential exists for tests.
    In production, this will be created by the installer team.
    """
    from aap_eda.core.utils.credentials import inputs_to_store

    # Check if the default system credential already exists
    default_credential = models.EdaCredential.objects.filter(
        name=settings.DEFAULT_SYSTEM_RULE_ENGINE_CREDENTIAL_NAME
    ).first()

    # Only create if it doesn't exist
    if default_credential is None:
        rule_engine_cred_type = models.CredentialType.objects.get(
            name=enums.DefaultCredentialType.EDA_RULE_ENGINE
        )
        default_credential = models.EdaCredential.objects.create(
            name=settings.DEFAULT_SYSTEM_RULE_ENGINE_CREDENTIAL_NAME,
            credential_type=rule_engine_cred_type,
            inputs=inputs_to_store(
                {
                    "postgres_db_host": "localhost",
                    "postgres_db_port": "5432",
                    "postgres_db_name": "testdb",
                    "postgres_db_user": "testuser",
                    "postgres_db_password": "testpass",
                    "postgres_sslmode": "prefer",
                    "primary_encryption_secret": "secret123secret",
                }
            ),
            organization=organization,
        )

    return default_credential


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_create_activation(
    mock_health_check,
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
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_create_activation_blank_text(
    mock_health_check,
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
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_create_activation_with_valid_extra_var(
    mock_health_check,
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
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_create_activation_with_vault_extra_var(
    mock_health_check,
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
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_delete_activation(
    mock_health_check,
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
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_restart_activation(
    mock_health_check,
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


@pytest.mark.django_db
@pytest.mark.parametrize("action", [enums.Action.RESTART, enums.Action.ENABLE])
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_restart_activation_without_de(
    mock_health_check,
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
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_enable_activation(
    mock_health_check,
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


@pytest.mark.django_db
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_disable_activation(
    mock_health_check,
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    response = admin_client.post(
        f"{api_url_v1}/activations/{default_activation.id}/disable/"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("force_disable", "expected_response"),
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
def test_disable_activation_workers_offline(
    force_disable,
    expected_response,
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    default_activation.status = enums.ActivationStatus.WORKERS_OFFLINE
    default_activation.save(update_fields=["status"])

    response = admin_client.post(
        f"{api_url_v1}/activations/{default_activation.id}/disable/"
        f"?force={force_disable}"
    )
    assert response.status_code == expected_response


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("force_delete", "expected_response"),
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
def test_delete_activation_workers_offline(
    force_delete,
    expected_response,
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    default_activation.status = enums.ActivationStatus.WORKERS_OFFLINE
    default_activation.save(update_fields=["status"])

    response = admin_client.delete(
        f"{api_url_v1}/activations/{default_activation.id}/"
        f"?force={force_delete}"
    )
    assert response.status_code == expected_response


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
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_create_activation_no_token_no_required(
    mock_health_check,
    activation_payload,
    admin_client: APIClient,
    preseed_credential_types,
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
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_restart_activation_with_required_token_deleted(
    mock_health_check,
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
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_create_activation_with_awx_token(
    mock_health_check,
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
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_create_activation_with_skip_audit_events(
    mock_health_check,
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
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_activation_by_fields(
    mock_health_check,
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
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_update_activation(
    mock_health_check,
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
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_update_enabled_activation(
    mock_health_check,
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
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_copy_activation(
    mock_health_check,
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
    assert activation.log_tracking_id is not None


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


# ------------------------------------------------------------------
# Project sync dependency tests
# ------------------------------------------------------------------


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@mock.patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
)
@mock.patch("aap_eda.api.views.activation.sync_project")
def test_enable_triggers_sync_when_project_needs_update(
    mock_sync,
    mock_health,
    default_activation: models.Activation,
    default_project: models.Project,
    admin_client: APIClient,
    preseed_credential_types,
):
    """Enable triggers sync when project needs update on launch."""
    mock_sync.return_value = "task-uuid"
    default_project.update_revision_on_launch = True
    default_project.scm_update_cache_timeout = 0
    default_project.save(
        update_fields=[
            "update_revision_on_launch",
            "scm_update_cache_timeout",
        ]
    )
    default_activation.is_enabled = False
    default_activation.status = enums.ActivationStatus.STOPPED
    default_activation.save(update_fields=["is_enabled", "status"])

    response = admin_client.post(
        f"{api_url_v1}/activations/" f"{default_activation.id}/enable/"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    default_activation.refresh_from_db()
    assert default_activation.awaiting_project_sync is True
    assert default_activation.status == enums.ActivationStatus.PENDING
    mock_sync.assert_called_once_with(default_project.id)


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@mock.patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
)
@mock.patch("aap_eda.api.views.activation.sync_project")
def test_enable_skips_sync_when_project_already_syncing(
    mock_sync,
    mock_health,
    default_activation: models.Activation,
    default_project: models.Project,
    admin_client: APIClient,
    preseed_credential_types,
):
    """Enable sets flag but skips sync_project when already running."""
    default_project.update_revision_on_launch = True
    default_project.scm_update_cache_timeout = 0
    default_project.import_state = models.Project.ImportState.RUNNING
    default_project.save(
        update_fields=[
            "update_revision_on_launch",
            "scm_update_cache_timeout",
            "import_state",
        ]
    )
    default_activation.is_enabled = False
    default_activation.status = enums.ActivationStatus.STOPPED
    default_activation.save(update_fields=["is_enabled", "status"])

    response = admin_client.post(
        f"{api_url_v1}/activations/" f"{default_activation.id}/enable/"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    default_activation.refresh_from_db()
    assert default_activation.awaiting_project_sync is True
    mock_sync.assert_not_called()


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@mock.patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
)
def test_enable_proceeds_normally_without_sync(
    mock_health,
    default_activation: models.Activation,
    default_project: models.Project,
    admin_client: APIClient,
    preseed_credential_types,
):
    """Enable returns 204 when project doesn't need sync."""
    default_project.update_revision_on_launch = False
    default_project.save(update_fields=["update_revision_on_launch"])
    default_activation.is_enabled = False
    default_activation.status = enums.ActivationStatus.STOPPED
    default_activation.save(update_fields=["is_enabled", "status"])

    response = admin_client.post(
        f"{api_url_v1}/activations/" f"{default_activation.id}/enable/"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    default_activation.refresh_from_db()
    assert default_activation.awaiting_project_sync is False
    assert default_activation.is_enabled is True


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@mock.patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
)
@mock.patch("aap_eda.api.views.activation.sync_project")
def test_restart_triggers_sync_when_project_needs_update(
    mock_sync,
    mock_health,
    default_activation: models.Activation,
    default_project: models.Project,
    admin_client: APIClient,
    preseed_credential_types,
):
    """Restart triggers sync when project needs update."""
    mock_sync.return_value = "task-uuid"
    default_project.update_revision_on_launch = True
    default_project.scm_update_cache_timeout = 0
    default_project.save(
        update_fields=[
            "update_revision_on_launch",
            "scm_update_cache_timeout",
        ]
    )
    default_activation.is_enabled = True
    default_activation.status = enums.ActivationStatus.RUNNING
    default_activation.save(update_fields=["is_enabled", "status"])

    response = admin_client.post(
        f"{api_url_v1}/activations/" f"{default_activation.id}/restart/"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    default_activation.refresh_from_db()
    assert default_activation.awaiting_project_sync is True
    mock_sync.assert_called_once_with(default_project.id)


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@mock.patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
)
@mock.patch("aap_eda.api.views.activation.sync_project")
def test_enable_sync_failure_resets_flag(
    mock_sync,
    mock_health,
    default_activation: models.Activation,
    default_project: models.Project,
    admin_client: APIClient,
    preseed_credential_types,
):
    """Enable resets flag and returns error when sync_project throws."""
    mock_sync.side_effect = RuntimeError("dispatcherd down")
    default_project.update_revision_on_launch = True
    default_project.scm_update_cache_timeout = 0
    default_project.save(
        update_fields=[
            "update_revision_on_launch",
            "scm_update_cache_timeout",
        ]
    )
    default_activation.is_enabled = False
    default_activation.status = enums.ActivationStatus.STOPPED
    default_activation.save(update_fields=["is_enabled", "status"])

    response = admin_client.post(
        f"{api_url_v1}/activations/" f"{default_activation.id}/enable/"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    default_activation.refresh_from_db()
    assert default_activation.awaiting_project_sync is False
    assert default_activation.status == (enums.ActivationStatus.ERROR)


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@mock.patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
)
@mock.patch("aap_eda.api.views.activation.sync_project")
def test_disable_clears_awaiting_project_sync(
    mock_sync,
    mock_health,
    default_activation: models.Activation,
    default_project: models.Project,
    admin_client: APIClient,
    preseed_credential_types,
):
    """Disable clears awaiting_project_sync flag."""
    mock_sync.return_value = "task-uuid"
    default_project.update_revision_on_launch = True
    default_project.scm_update_cache_timeout = 0
    default_project.save(
        update_fields=[
            "update_revision_on_launch",
            "scm_update_cache_timeout",
        ]
    )
    default_activation.is_enabled = False
    default_activation.status = enums.ActivationStatus.STOPPED
    default_activation.save(update_fields=["is_enabled", "status"])
    response = admin_client.post(
        f"{api_url_v1}/activations/" f"{default_activation.id}/enable/"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Set is_enabled so disable logic runs
    default_activation.refresh_from_db()
    default_activation.is_enabled = True
    default_activation.save(update_fields=["is_enabled"])

    response = admin_client.post(
        f"{api_url_v1}/activations/" f"{default_activation.id}/disable/"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    default_activation.refresh_from_db()
    assert default_activation.awaiting_project_sync is False
    assert default_activation.is_enabled is False


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@mock.patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
)
def test_destroy_clears_awaiting_project_sync(
    mock_health,
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    """Destroy clears awaiting_project_sync flag."""
    default_activation.awaiting_project_sync = True
    default_activation.save(update_fields=["awaiting_project_sync"])

    response = admin_client.delete(
        f"{api_url_v1}/activations/" f"{default_activation.id}/"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_activation_detail_shows_warning_on_rulebook_drift(
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    """Warnings show when rulebook SHA256 drifts from activation."""
    old_hash = get_rulebook_hash("old-content")
    default_activation.source_mappings = "[{source: src1, event_stream: es1}]"
    default_activation.rulebook_rulesets_sha256 = old_hash
    default_activation.save(
        update_fields=[
            "source_mappings",
            "rulebook_rulesets_sha256",
        ]
    )

    # Simulate rulebook drift by updating the rulebook's SHA
    rulebook = default_activation.rulebook
    rulebook.rulesets_sha256 = get_rulebook_hash("new-content")
    rulebook.save(update_fields=["rulesets_sha256"])

    response = admin_client.get(
        f"{api_url_v1}/activations/{default_activation.id}/"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["warnings"]) == 1
    assert "source mappings" in response.data["warnings"][0]


@pytest.mark.django_db
def test_activation_detail_no_warning_when_hashes_match(
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    """No warnings when activation and rulebook SHA256 match."""
    matching_hash = get_rulebook_hash("same-content")
    default_activation.source_mappings = "[{source: src1, event_stream: es1}]"
    default_activation.rulebook_rulesets_sha256 = matching_hash
    default_activation.save(
        update_fields=[
            "source_mappings",
            "rulebook_rulesets_sha256",
        ]
    )

    rulebook = default_activation.rulebook
    rulebook.rulesets_sha256 = matching_hash
    rulebook.save(update_fields=["rulesets_sha256"])

    response = admin_client.get(
        f"{api_url_v1}/activations/{default_activation.id}/"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["warnings"] == []


@pytest.mark.django_db
def test_activation_detail_no_warning_without_source_mappings(
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    """No warnings when activation has no source_mappings."""
    default_activation.source_mappings = ""
    default_activation.rulebook_rulesets_sha256 = get_rulebook_hash(
        "old-content"
    )
    default_activation.save(
        update_fields=[
            "source_mappings",
            "rulebook_rulesets_sha256",
        ]
    )

    rulebook = default_activation.rulebook
    rulebook.rulesets_sha256 = get_rulebook_hash("new-content")
    rulebook.save(update_fields=["rulesets_sha256"])

    response = admin_client.get(
        f"{api_url_v1}/activations/{default_activation.id}/"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["warnings"] == []


@pytest.mark.django_db
def test_list_activations_does_not_include_warnings(
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    """List endpoint does not include warnings field."""
    default_activation.source_mappings = "[{source: src1, event_stream: es1}]"
    default_activation.rulebook_rulesets_sha256 = get_rulebook_hash(
        "old-content"
    )
    default_activation.save(
        update_fields=[
            "source_mappings",
            "rulebook_rulesets_sha256",
        ]
    )

    rulebook = default_activation.rulebook
    rulebook.rulesets_sha256 = get_rulebook_hash("new-content")
    rulebook.save(update_fields=["rulesets_sha256"])

    response = admin_client.get(f"{api_url_v1}/activations/")
    assert response.status_code == status.HTTP_200_OK
    for result in response.data["results"]:
        assert "warnings" not in result


@pytest.mark.django_db
def test_activation_detail_warning_on_deleted_rulebook(
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    """Warning when rulebook is deleted but source_mappings exist."""
    default_activation.source_mappings = "[{source: src1, event_stream: es1}]"
    default_activation.rulebook_rulesets_sha256 = get_rulebook_hash(
        "old-content"
    )
    default_activation.rulebook = None
    default_activation.save(
        update_fields=[
            "source_mappings",
            "rulebook_rulesets_sha256",
            "rulebook",
        ]
    )

    response = admin_client.get(
        f"{api_url_v1}/activations/{default_activation.id}/"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["warnings"]) == 1
    assert "no longer exists" in response.data["warnings"][0]


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_create_activation_with_enable_persistence(
    mock_health_check,
    admin_awx_token: models.AwxToken,
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    # Ensure default rule engine credential exists for persistence tests
    ensure_default_rule_engine_credential(default_organization)

    activation_payload["enable_persistence"] = True
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.data
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert activation.enable_persistence is True
    assert data["enable_persistence"] is True


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_create_activation_with_enable_persistence_false(
    mock_health_check,
    admin_awx_token: models.AwxToken,
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
):
    activation_payload["enable_persistence"] = False
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.data
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert activation.enable_persistence is False
    assert data["enable_persistence"] is False


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_create_activation_with_rule_engine_credential(
    mock_health_check,
    admin_awx_token: models.AwxToken,
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    # Create an EDA Rule Engine credential
    rule_engine_cred_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.EDA_RULE_ENGINE
    )
    rule_engine_credential = models.EdaCredential.objects.create(
        name="test-rule-engine-credential",
        credential_type=rule_engine_cred_type,
        inputs={
            "primary_key": "test_primary_key_value",
            "secondary_key": "test_secondary_key_value",
            "aes_salt": "test_salt_value",
        },
        organization=default_organization,
    )

    activation_payload["rule_engine_credential_id"] = rule_engine_credential.id
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.data
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert activation.rule_engine_credential.id == rule_engine_credential.id
    assert data["rule_engine_credential_id"] == rule_engine_credential.id


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_update_activation_enable_persistence(
    mock_health_check,
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    # Ensure default rule engine credential exists for persistence tests
    ensure_default_rule_engine_credential(default_organization)

    # Create activation with is_enabled=False so we can update it
    activation_payload["is_enabled"] = False
    activation_payload["enable_persistence"] = False
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    activation_id = response.data["id"]

    # Update enable_persistence to True
    response = admin_client.patch(
        f"{api_url_v1}/activations/{activation_id}/",
        data={"enable_persistence": True},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["enable_persistence"] is True

    # Verify in database
    activation = models.Activation.objects.get(id=activation_id)
    assert activation.enable_persistence is True


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_update_activation_rule_engine_credential(
    mock_health_check,
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    # Create an EDA Rule Engine credential
    rule_engine_cred_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.EDA_RULE_ENGINE
    )
    rule_engine_credential = models.EdaCredential.objects.create(
        name="test-rule-engine-credential",
        credential_type=rule_engine_cred_type,
        inputs={
            "postgres_db_host": "localhost",
            "postgres_db_name": "testdb",
            "primary_encryption_secret": "test_primary_key_value",
            "secondary_encryption_secret": "test_secondary_key_value",
        },
        organization=default_organization,
    )

    # Create activation with is_enabled=False so we can update it
    activation_payload["is_enabled"] = False
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    activation_id = response.data["id"]

    # Update to set the rule_engine_credential
    response = admin_client.patch(
        f"{api_url_v1}/activations/{activation_id}/",
        data={"rule_engine_credential_id": rule_engine_credential.id},
    )
    assert response.status_code == status.HTTP_200_OK
    assert (
        response.data["rule_engine_credential_id"] == rule_engine_credential.id
    )

    # Verify in database
    activation = models.Activation.objects.get(id=activation_id)
    assert activation.rule_engine_credential.id == rule_engine_credential.id


@pytest.mark.django_db
def test_list_activation_includes_persistence_fields(
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    # Create an EDA Rule Engine credential with required fields
    rule_engine_cred_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.EDA_RULE_ENGINE
    )
    rule_engine_credential = models.EdaCredential.objects.create(
        name="test-rule-engine-credential",
        credential_type=rule_engine_cred_type,
        inputs={
            "postgres_db_host": "localhost",
            "postgres_db_name": "testdb",
            "primary_encryption_secret": "test_primary_key_value",
        },
        organization=default_organization,
    )

    default_activation.enable_persistence = True
    default_activation.rule_engine_credential = rule_engine_credential
    default_activation.save(
        update_fields=["enable_persistence", "rule_engine_credential"]
    )

    response = admin_client.get(f"{api_url_v1}/activations/")
    assert response.status_code == status.HTTP_200_OK

    # Find our activation in the results
    activation_data = next(
        (
            item
            for item in response.data["results"]
            if item["id"] == default_activation.id
        ),
        None,
    )
    assert activation_data is not None
    assert activation_data["enable_persistence"] is True
    assert (
        activation_data["rule_engine_credential_id"]
        == rule_engine_credential.id
    )


@pytest.mark.django_db
def test_read_activation_includes_persistence_fields(
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    # Create an EDA Rule Engine credential with required fields
    rule_engine_cred_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.EDA_RULE_ENGINE
    )
    rule_engine_credential = models.EdaCredential.objects.create(
        name="test-rule-engine-credential",
        credential_type=rule_engine_cred_type,
        inputs={
            "postgres_db_host": "localhost",
            "postgres_db_name": "testdb",
            "primary_encryption_secret": "test_primary_key_value",
        },
        organization=default_organization,
    )

    default_activation.enable_persistence = True
    default_activation.rule_engine_credential = rule_engine_credential
    default_activation.save(
        update_fields=["enable_persistence", "rule_engine_credential"]
    )

    response = admin_client.get(
        f"{api_url_v1}/activations/{default_activation.id}/"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["enable_persistence"] is True
    assert (
        response.data["rule_engine_credential_id"] == rule_engine_credential.id
    )
    # Verify the full credential object is returned
    assert response.data["rule_engine_credential"] is not None
    assert response.data["rule_engine_credential"]["id"] == (
        rule_engine_credential.id
    )
    assert response.data["rule_engine_credential"]["name"] == (
        rule_engine_credential.name
    )


@pytest.mark.django_db
def test_create_activation_persistence_without_credential_or_default(
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
):
    """Test that creating an activation with enable_persistence=True fails
    when no rule_engine_credential_id is provided and no default
    credential exists.
    """
    activation_payload["enable_persistence"] = True
    # Don't provide rule_engine_credential_id and ensure no default exists
    # The default credential should not exist in a fresh test database

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.data
    error_message = str(response.data["non_field_errors"][0])
    assert "Persistence is enabled" in error_message
    assert "Please provide a rule_engine_credential_id." in error_message


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_create_activation_persistence_with_credential_provided(
    mock_health_check,
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    """Test that creating an activation with enable_persistence=True succeeds
    when rule_engine_credential_id is provided."""
    from aap_eda.core.utils.credentials import inputs_to_store

    rule_engine_cred_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.EDA_RULE_ENGINE
    )
    rule_engine_credential = models.EdaCredential.objects.create(
        name="custom-rule-engine-credential",
        credential_type=rule_engine_cred_type,
        inputs=inputs_to_store(
            {
                "postgres_db_host": "localhost",
                "postgres_db_port": "5432",
                "postgres_db_name": "testdb",
                "postgres_db_user": "testuser",
                "postgres_db_password": "testpass",
                "postgres_sslmode": "prefer",
                "primary_encryption_secret": "secret123secret",
            }
        ),
        organization=default_organization,
    )

    activation_payload["enable_persistence"] = True
    activation_payload["rule_engine_credential_id"] = rule_engine_credential.id

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["enable_persistence"] is True
    assert (
        response.data["rule_engine_credential_id"] == rule_engine_credential.id
    )


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_create_activation_persistence_with_default_credential(
    mock_health_check,
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    """Test that creating an activation with enable_persistence=True succeeds
    when a default system credential exists.
    """
    # Ensure default rule engine credential exists for persistence tests
    ensure_default_rule_engine_credential(default_organization)

    activation_payload["enable_persistence"] = True
    # Don't provide rule_engine_credential_id - should use default

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["enable_persistence"] is True


@pytest.mark.django_db
def test_update_activation_persistence_without_credential_or_default(
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
):
    """Test that updating an activation to enable_persistence=True fails
    when no rule_engine_credential_id is provided and no default
    credential exists.
    """
    # Create activation with is_enabled=False and persistence disabled
    activation_payload["is_enabled"] = False
    activation_payload["enable_persistence"] = False
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    activation_id = response.data["id"]

    # Try to update to enable persistence without providing credential
    response = admin_client.patch(
        f"{api_url_v1}/activations/{activation_id}/",
        data={"enable_persistence": True},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.data
    error_message = str(response.data["non_field_errors"][0])
    assert "Persistence is enabled" in error_message
    assert "Please provide a rule_engine_credential_id." in error_message


@pytest.mark.django_db
def test_create_activation_persistence_with_invalid_credential_id(
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
):
    """Test that creating an activation with enable_persistence=True and
    an invalid rule_engine_credential_id fails."""
    activation_payload["enable_persistence"] = True
    activation_payload["rule_engine_credential_id"] = 99999  # Non-existent ID

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.data
    error_message = str(response.data["non_field_errors"][0])
    assert "EdaCredential with id 99999 does not exist" in error_message


@pytest.mark.django_db
def test_create_activation_persistence_with_wrong_namespace(
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    """Test that creating an activation with enable_persistence=True and
    a credential with wrong namespace fails."""
    from aap_eda.core.utils.credentials import inputs_to_store

    # Create a credential type with a different namespace
    wrong_cred_type = models.CredentialType.objects.create(
        name="Wrong Namespace Credential Type",
        namespace="wrong_namespace",
        kind="cloud",
        inputs={
            "fields": [
                {"id": "test_field", "label": "Test Field", "type": "string"}
            ]
        },
        injectors={},
    )

    # Create a credential with the wrong namespace
    wrong_credential = models.EdaCredential.objects.create(
        name="wrong-namespace-credential",
        credential_type=wrong_cred_type,
        inputs=inputs_to_store({"test_field": "test_value"}),
        organization=default_organization,
    )

    activation_payload["enable_persistence"] = True
    activation_payload["rule_engine_credential_id"] = wrong_credential.id

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.data
    error_message = str(response.data["non_field_errors"][0])
    assert "namespace 'drools'" in error_message
    assert "wrong_namespace" in error_message


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_create_activation_with_credential_and_persistence_credential_count(
    mock_health_check,
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    """Test credential handling with both regular and rule engine credentials.

    When creating an activation with:
    - A regular credential (e.g., AAP) in eda_credentials list
    - Persistence enabled with a rule_engine_credential

    Expected behavior (after fix):
    - The AAP credential is stored in the eda_credentials M2M
      relationship
    - The rule engine credential is ONLY stored in
      rule_engine_credential FK field
    - The rule engine credential is NOT added to eda_credentials M2M

    The rule engine credential appears in ONE place:
    - In the rule_engine_credential foreign key field ONLY

    This ensures clean separation between regular credentials and persistence
    credentials, avoiding orphaned credentials during updates.

    Related tests:
    - test_update_activation_disable_persistence_removes_rule_engine_credential
      (no cleanup needed since never added)
    - test_update_activation_change_rule_engine_credential
      (no cleanup needed)
    """
    from aap_eda.core.utils.credentials import inputs_to_store

    # Create a regular AAP credential
    aap_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.AAP
    )
    aap_credential = models.EdaCredential.objects.create(
        name="test-aap-credential",
        credential_type=aap_credential_type,
        inputs=inputs_to_store(
            {
                "host": "https://controller.example.com",
                "username": "testuser",
                "password": "testpass",
            }
        ),
        organization=default_organization,
    )

    # Create a rule engine credential
    rule_engine_cred_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.EDA_RULE_ENGINE
    )
    rule_engine_credential = models.EdaCredential.objects.create(
        name="test-rule-engine-credential",
        credential_type=rule_engine_cred_type,
        inputs=inputs_to_store(
            {
                "postgres_db_host": "localhost",
                "postgres_db_port": "5432",
                "postgres_db_name": "testdb",
                "postgres_db_user": "testuser",
                "postgres_db_password": "testpass",
                "postgres_sslmode": "prefer",
                "primary_encryption_secret": "secret123secret",
            }
        ),
        organization=default_organization,
    )

    # Create activation with both regular credential and persistence enabled
    activation_payload["eda_credentials"] = [aap_credential.id]
    activation_payload["enable_persistence"] = True
    activation_payload["rule_engine_credential_id"] = rule_engine_credential.id

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED

    # Verify the activation in the database
    activation = models.Activation.objects.get(id=response.data["id"])

    # Check eda_credentials - should ONLY contain the AAP credential
    all_eda_credentials = list(activation.eda_credentials.all())
    eda_credential_ids = [cred.id for cred in all_eda_credentials]

    # After fix: Only regular credentials are in eda_credentials
    assert len(all_eda_credentials) == 1, (
        f"Expected 1 credential in eda_credentials "
        f"(only AAP), got {len(all_eda_credentials)}: {eda_credential_ids}"
    )
    assert (
        aap_credential.id in eda_credential_ids
    ), "AAP credential should be in eda_credentials"
    assert rule_engine_credential.id not in eda_credential_ids, (
        "Rule engine credential should NOT be in eda_credentials - "
        "it should only be in the rule_engine_credential FK field"
    )

    # Verify persistence is enabled and rule_engine_credential field is set
    # The rule engine credential is ONLY in the FK field, not in M2M
    assert activation.enable_persistence is True
    assert activation.rule_engine_credential is not None
    assert activation.rule_engine_credential.id == rule_engine_credential.id

    # Verify the API response
    assert response.data["enable_persistence"] is True
    assert (
        response.data["rule_engine_credential_id"] == rule_engine_credential.id
    )

    # Response eda_credentials should show only the AAP credential
    response_credential_ids = [
        cred["id"] for cred in response.data["eda_credentials"]
    ]
    assert len(response.data["eda_credentials"]) == 1, (
        f"Only AAP credential should appear in response, "
        f"got {len(response.data['eda_credentials'])}"
    )
    assert aap_credential.id in response_credential_ids
    assert (
        rule_engine_credential.id not in response_credential_ids
    ), "Rule engine credential should NOT be in response eda_credentials"


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_update_activation_disable_persistence_removes_rule_engine_credential(
    mock_health_check,
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    """Test that disabling persistence clears rule engine credential.

    This test verifies that when an activation with persistence is
    updated to disable persistence:
    1. The rule_engine_credential FK field is cleared (set to None)
    2. Regular credentials (AAP) remain in eda_credentials unchanged
    3. No orphaned credentials are left behind

    Since rule engine credentials are only stored in the FK field
    (not in eda_credentials M2M), disabling persistence is clean.
    """
    from aap_eda.core.utils.credentials import inputs_to_store

    # Create an AAP credential
    aap_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.AAP
    )
    aap_credential = models.EdaCredential.objects.create(
        name="test-aap-credential",
        credential_type=aap_credential_type,
        inputs=inputs_to_store(
            {
                "host": "https://controller.example.com",
                "username": "testuser",
                "password": "testpass",
            }
        ),
        organization=default_organization,
    )

    # Create a rule engine credential
    rule_engine_cred_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.EDA_RULE_ENGINE
    )
    rule_engine_credential = models.EdaCredential.objects.create(
        name="test-rule-engine-credential",
        credential_type=rule_engine_cred_type,
        inputs=inputs_to_store(
            {
                "postgres_db_host": "localhost",
                "postgres_db_port": "5432",
                "postgres_db_name": "testdb",
                "postgres_db_user": "testuser",
                "postgres_db_password": "testpass",
                "postgres_sslmode": "prefer",
                "primary_encryption_secret": "secret123secret",
            }
        ),
        organization=default_organization,
    )

    # Create activation with AAP credential AND persistence enabled
    activation_payload["is_enabled"] = False  # Must be disabled to update
    activation_payload["eda_credentials"] = [aap_credential.id]
    activation_payload["enable_persistence"] = True
    activation_payload["rule_engine_credential_id"] = rule_engine_credential.id

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    activation_id = response.data["id"]

    # Verify initial state
    activation = models.Activation.objects.get(id=activation_id)
    initial_creds = list(activation.eda_credentials.all())

    # Now disable persistence
    update_response = admin_client.patch(
        f"{api_url_v1}/activations/{activation_id}/",
        data={
            "enable_persistence": False,
            "rule_engine_credential_id": None,
        },
    )
    assert update_response.status_code == status.HTTP_200_OK

    # Check what happened to the credentials
    activation.refresh_from_db()
    updated_creds = list(activation.eda_credentials.all())

    # Verify persistence was disabled and FK field cleared
    assert activation.enable_persistence is False
    assert activation.rule_engine_credential is None

    # Verify credentials are properly maintained
    initial_cred_ids = [c.id for c in initial_creds]
    updated_cred_ids = [c.id for c in updated_creds]

    # The AAP credential should remain unchanged
    assert (
        aap_credential.id in updated_cred_ids
    ), "AAP credential should remain in eda_credentials after update"

    # Verify rule engine credential was never in eda_credentials
    assert rule_engine_credential.id not in initial_cred_ids, (
        "Rule engine credential should only be in FK field, "
        "not in eda_credentials"
    )
    assert rule_engine_credential.id not in updated_cred_ids, (
        "Rule engine credential should not be in eda_credentials "
        "after update"
    )

    # Verify no credentials were lost or orphaned
    assert (
        len(initial_creds) == len(updated_creds) == 1
    ), "Should have exactly 1 credential (AAP) before and after"


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_update_activation_enable_persistence_with_rule_engine_credential(
    mock_health_check,
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    """Test enabling persistence and adding rule engine credential.

    This test verifies that when an activation without persistence is
    updated to enable persistence and add a rule engine credential:
    1. The enable_persistence field is set to True
    2. The rule_engine_credential FK field is set to the new credential
    3. Regular credentials (AAP) remain in eda_credentials unchanged
    4. Rule engine credential is only in the FK field, not in eda_credentials
    """
    from aap_eda.core.utils.credentials import inputs_to_store

    # Create an AAP credential
    aap_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.AAP
    )
    aap_credential = models.EdaCredential.objects.create(
        name="test-aap-credential",
        credential_type=aap_credential_type,
        inputs=inputs_to_store(
            {
                "host": "https://controller.example.com",
                "username": "testuser",
                "password": "testpass",
            }
        ),
        organization=default_organization,
    )

    # Create a rule engine credential
    rule_engine_cred_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.EDA_RULE_ENGINE
    )
    rule_engine_credential = models.EdaCredential.objects.create(
        name="test-rule-engine-credential",
        credential_type=rule_engine_cred_type,
        inputs=inputs_to_store(
            {
                "postgres_db_host": "localhost",
                "postgres_db_port": "5432",
                "postgres_db_name": "testdb",
                "postgres_db_user": "testuser",
                "postgres_db_password": "testpass",
                "postgres_sslmode": "prefer",
                "primary_encryption_secret": "secret123secret",
            }
        ),
        organization=default_organization,
    )

    # Create activation WITHOUT persistence enabled
    activation_payload["is_enabled"] = False  # Must be disabled to update
    activation_payload["eda_credentials"] = [aap_credential.id]
    activation_payload["enable_persistence"] = False

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    activation_id = response.data["id"]

    # Verify initial state - no persistence, no rule engine credential
    activation = models.Activation.objects.get(id=activation_id)
    assert activation.enable_persistence is False
    assert activation.rule_engine_credential is None
    initial_creds = list(activation.eda_credentials.all())
    assert len(initial_creds) == 1
    assert initial_creds[0].id == aap_credential.id

    # Now enable persistence and add rule engine credential
    update_response = admin_client.patch(
        f"{api_url_v1}/activations/{activation_id}/",
        data={
            "enable_persistence": True,
            "rule_engine_credential_id": rule_engine_credential.id,
        },
    )
    assert update_response.status_code == status.HTTP_200_OK

    # Verify the update
    activation.refresh_from_db()

    # Check persistence is enabled and rule_engine_credential FK field is set
    assert activation.enable_persistence is True
    assert activation.rule_engine_credential is not None
    assert activation.rule_engine_credential.id == rule_engine_credential.id

    # Check eda_credentials - should ONLY contain the AAP credential
    updated_creds = list(activation.eda_credentials.all())
    updated_cred_ids = [c.id for c in updated_creds]

    assert len(updated_creds) == 1, (
        f"Expected 1 credential in eda_credentials (only AAP), "
        f"got {len(updated_creds)}: {updated_cred_ids}"
    )
    assert (
        aap_credential.id in updated_cred_ids
    ), "AAP credential should remain in eda_credentials"
    assert rule_engine_credential.id not in updated_cred_ids, (
        "Rule engine credential should NOT be in eda_credentials - "
        "it should only be in the rule_engine_credential FK field"
    )

    # Verify the API response
    assert update_response.data["enable_persistence"] is True
    assert (
        update_response.data["rule_engine_credential_id"]
        == rule_engine_credential.id
    )

    # Response eda_credentials should show only the AAP credential
    response_credential_ids = [
        cred["id"] for cred in update_response.data["eda_credentials"]
    ]
    assert len(update_response.data["eda_credentials"]) == 1, (
        f"Only AAP credential should appear in response, "
        f"got {len(update_response.data['eda_credentials'])}"
    )
    assert aap_credential.id in response_credential_ids
    assert (
        rule_engine_credential.id not in response_credential_ids
    ), "Rule engine credential should NOT be in response eda_credentials"


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_update_activation_change_rule_engine_credential(
    mock_health_check,
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    """Test changing from one rule engine credential to another.

    This test verifies that when switching rule engine credentials:
    1. The rule_engine_credential FK field is updated to the new credential
    2. Regular credentials (AAP) in eda_credentials remain unchanged
    3. Neither old nor new rule engine credentials appear in eda_credentials
    4. The change is clean with no orphaned or duplicate credentials

    Since rule engine credentials are only stored in the FK field, changing
    them is a simple field update without affecting the M2M relationship.
    """
    from aap_eda.core.utils.credentials import inputs_to_store

    # Create an AAP credential
    aap_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.AAP
    )
    aap_credential = models.EdaCredential.objects.create(
        name="test-aap-credential",
        credential_type=aap_credential_type,
        inputs=inputs_to_store(
            {
                "host": "https://controller.example.com",
                "username": "testuser",
                "password": "testpass",
            }
        ),
        organization=default_organization,
    )

    # Create first rule engine credential
    rule_engine_cred_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.EDA_RULE_ENGINE
    )
    rule_engine_credential_1 = models.EdaCredential.objects.create(
        name="test-rule-engine-credential-1",
        credential_type=rule_engine_cred_type,
        inputs=inputs_to_store(
            {
                "postgres_db_host": "localhost",
                "postgres_db_port": "5432",
                "postgres_db_name": "testdb1",
                "postgres_db_user": "testuser",
                "postgres_db_password": "testpass",
                "postgres_sslmode": "prefer",
                "primary_encryption_secret": "secret123secret",
            }
        ),
        organization=default_organization,
    )

    # Create second rule engine credential
    rule_engine_credential_2 = models.EdaCredential.objects.create(
        name="test-rule-engine-credential-2",
        credential_type=rule_engine_cred_type,
        inputs=inputs_to_store(
            {
                "postgres_db_host": "localhost",
                "postgres_db_port": "5432",
                "postgres_db_name": "testdb2",
                "postgres_db_user": "testuser",
                "postgres_db_password": "testpass",
                "postgres_sslmode": "prefer",
                "primary_encryption_secret": "secret456secret",
            }
        ),
        organization=default_organization,
    )

    # Create activation with AAP credential AND first rule engine credential
    activation_payload["is_enabled"] = False  # Must be disabled to update
    activation_payload["eda_credentials"] = [aap_credential.id]
    activation_payload["enable_persistence"] = True
    activation_payload[
        "rule_engine_credential_id"
    ] = rule_engine_credential_1.id

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    activation_id = response.data["id"]

    # Verify initial state
    activation = models.Activation.objects.get(id=activation_id)
    initial_creds = list(activation.eda_credentials.all())
    initial_cred_ids = [c.id for c in initial_creds]

    # Now change to the second rule engine credential
    update_response = admin_client.patch(
        f"{api_url_v1}/activations/{activation_id}/",
        data={
            "rule_engine_credential_id": rule_engine_credential_2.id,
        },
    )
    assert update_response.status_code == status.HTTP_200_OK

    # Check what happened to the credentials
    activation.refresh_from_db()
    updated_creds = list(activation.eda_credentials.all())
    updated_cred_ids = [c.id for c in updated_creds]

    # Verify the FK field was updated to the new credential
    assert activation.enable_persistence is True
    assert (
        activation.rule_engine_credential.id == rule_engine_credential_2.id
    ), "FK field should be updated to new rule engine credential"

    # Verify regular credentials remain unchanged
    assert (
        aap_credential.id in updated_cred_ids
    ), "AAP credential should remain in eda_credentials"

    # Verify neither old nor new rule engine credentials in eda_credentials
    assert (
        rule_engine_credential_1.id not in initial_cred_ids
    ), "Old rule engine credential should never be in eda_credentials"
    assert rule_engine_credential_1.id not in updated_cred_ids, (
        "Old rule engine credential should not be in eda_credentials "
        "after update"
    )
    assert (
        rule_engine_credential_2.id not in updated_cred_ids
    ), "New rule engine credential should not be in eda_credentials"

    # Verify no credentials were lost, duplicated, or orphaned
    assert (
        len(initial_cred_ids) == len(updated_cred_ids) == 1
    ), "Should have exactly 1 credential (AAP) before and after"
    assert initial_cred_ids == updated_cred_ids, (
        "eda_credentials should be unchanged when switching "
        "rule engine credentials"
    )


@pytest.mark.django_db
@mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
@patch(
    "aap_eda.api.views.activation.check_dispatcherd_workers_health",
    return_value=True,
)
def test_create_activation_with_only_rule_engine_credential(
    mock_health_check,
    activation_payload: Dict[str, Any],
    default_rulebook: models.Rulebook,
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    """Test creating activation with ONLY rule engine credential.

    This test verifies that rule engine credentials stay in the FK field
    and are not added to eda_credentials, even when there are no regular
    credentials.
    """
    from aap_eda.core.utils.credentials import inputs_to_store

    # Create a rule engine credential
    rule_engine_cred_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.EDA_RULE_ENGINE
    )
    rule_engine_credential = models.EdaCredential.objects.create(
        name="test-rule-engine-credential",
        credential_type=rule_engine_cred_type,
        inputs=inputs_to_store(
            {
                "postgres_db_host": "localhost",
                "postgres_db_port": "5432",
                "postgres_db_name": "testdb",
                "postgres_db_user": "testuser",
                "postgres_db_password": "testpass",
                "postgres_sslmode": "prefer",
                "primary_encryption_secret": "secret123secret",
            }
        ),
        organization=default_organization,
    )

    # Create activation with ONLY persistence (no eda_credentials)
    activation_payload["enable_persistence"] = True
    activation_payload["rule_engine_credential_id"] = rule_engine_credential.id
    # Explicitly NOT setting eda_credentials

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=activation_payload
    )
    assert response.status_code == status.HTTP_201_CREATED

    # Check what's in eda_credentials
    activation = models.Activation.objects.get(id=response.data["id"])
    all_creds = list(activation.eda_credentials.all())
    cred_ids = [c.id for c in all_creds]

    # Verify rule engine credential is only in FK field
    assert len(all_creds) == 0, (
        "eda_credentials should be empty when only rule engine "
        "credential is provided"
    )
    assert (
        rule_engine_credential.id not in cred_ids
    ), "Rule engine credential should not be in eda_credentials"
    assert activation.rule_engine_credential.id == (
        rule_engine_credential.id
    ), "Rule engine credential should be in FK field"
