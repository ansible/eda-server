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

from typing import Any, Dict, List

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import enums, models
from tests.integration.constants import api_url_v1

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


# ------------------------------------------
# Test Activation Instances:
# ------------------------------------------
@pytest.mark.django_db
def test_list_activation_instances(
    default_activation_instances: List[models.RulebookProcess],
    admin_client: APIClient,
):
    response = admin_client.get(f"{api_url_v1}/activation-instances/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == len(default_activation_instances)


@pytest.mark.django_db
def test_list_activation_instances_filter_name(
    default_activation_instances: List[models.RulebookProcess],
    admin_client: APIClient,
):
    filter_name = default_activation_instances[0].name
    response = admin_client.get(
        f"{api_url_v1}/activation-instances/?name={filter_name}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert (
        response.data["results"][0]["name"]
        == default_activation_instances[0].name
    )


@pytest.mark.django_db
def test_list_activation_instances_filter_status(
    default_activation_instances: List[models.RulebookProcess],
    admin_client: APIClient,
):
    filter_name = enums.ActivationStatus.FAILED
    response = admin_client.get(
        f"{api_url_v1}/activation-instances/?status={filter_name}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert (
        response.data["results"][0]["name"]
        == default_activation_instances[1].name
    )


@pytest.mark.django_db
def test_retrieve_activation_instance(
    default_activation_instances: List[models.RulebookProcess],
    admin_client: APIClient,
):
    instance = default_activation_instances[0]
    response = admin_client.get(
        f"{api_url_v1}/activation-instances/{instance.id}/"
    )

    assert response.status_code == status.HTTP_200_OK
    assert_activation_instance_data(response.json(), instance)


@pytest.mark.django_db
def test_retrieve_activation_instance_not_exist(admin_client: APIClient):
    response = admin_client.get(f"{api_url_v1}/activation-instances/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_list_logs_from_activation_instance(
    default_activation_instances: List[models.RulebookProcess],
    default_activation_instance_logs: List[models.RulebookProcessLog],
    admin_client: APIClient,
):
    instance = default_activation_instances[0]

    response = admin_client.get(
        f"{api_url_v1}/activation-instances/{instance.id}/logs/"
    )
    assert response.status_code == status.HTTP_200_OK
    response_logs = response.data["results"]

    assert len(response_logs) == 2
    assert response_logs[0]["log"] == "activation-instance-log-1"
    assert list(response_logs[0]) == [
        "id",
        "line_number",
        "log",
        "log_timestamp",
        "activation_instance",
    ]


@pytest.mark.django_db
def test_list_activation_instance_logs_filter(
    default_activation_instances: List[models.RulebookProcess],
    default_activation_instance_logs: List[models.RulebookProcessLog],
    admin_client: APIClient,
):
    instance = default_activation_instances[0]
    filter_log = "log-1"
    response = admin_client.get(
        f"{api_url_v1}/activation-instances/{instance.id}"
        f"/logs/?log={filter_log}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert (
        response.data["results"][0]["log"]
        == default_activation_instance_logs[0].log
    )


@pytest.mark.django_db
def test_list_activation_instance_logs_filter_non_existent(
    default_activation_instances: List[models.RulebookProcess],
    default_activation_instance_logs: List[models.RulebookProcessLog],
    admin_client: APIClient,
):
    instance = default_activation_instances[0]
    filter_log = "doesn't exist"

    response = admin_client.get(
        f"{api_url_v1}/activation-instances/{instance.id}"
        f"/logs/?log={filter_log}"
    )
    data = response.json()["results"]
    assert response.status_code == status.HTTP_200_OK
    assert data == []


def assert_activation_instance_data(
    data: Dict[str, Any], instance: models.RulebookProcess
):
    assert data == {
        "id": instance.id,
        "name": instance.name,
        "status": instance.status,
        "git_hash": instance.git_hash,
        "activation_id": instance.activation.id,
        "organization_id": instance.organization.id,
        "started_at": instance.started_at.strftime(DATETIME_FORMAT),
        "ended_at": instance.ended_at,
        "status_message": enums.ACTIVATION_STATUS_MESSAGE_MAP[instance.status],
        "event_stream_id": None,
        "queue_name": instance.rulebookprocessqueue.queue_name,
    }
