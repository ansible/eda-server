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

from dataclasses import dataclass
from typing import Any, Dict

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.constants import api_url_v1

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

TEST_RULESETS_SAMPLE = """
---
- name: Test sample 001
  hosts: all
  sources:
    - ansible.eda.range:
        limit: 5
        delay: 1
      filters:
        - noop:
  rules:
    - name: r1
      condition: event.i == 1
      action:
        debug:
    - name: r2
      condition: event.i == 2
      action:
        debug:

- name: Test sample 002
  hosts: all
  sources:
    - ansible.eda.range:
        limit: 5
        delay: 1
  rules:
    - name: r3
      condition: event.i == 2
      action:
        debug:
""".strip()

DUMMY_UUID = "8472ff2c-6045-4418-8d4e-46f6cffc8557"


@dataclass
class InitData:
    rulebook: models.Rulebook
    activation: models.Activation


# ------------------------------------------
# Test Activation Instances:
# ------------------------------------------
@pytest.mark.django_db
def test_list_activation_instances(client: APIClient):
    activation = prepare_init_data()
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
    response = client.get(f"{api_url_v1}/activation-instances/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == len(instances)


@pytest.mark.django_db
def test_list_activation_instances_filter_name(client: APIClient):
    activation = prepare_init_data()
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

    filter_name = "activation"
    response = client.get(
        f"{api_url_v1}/activation-instances/?name={filter_name}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["name"] == instances[0].name


@pytest.mark.django_db
def test_list_activation_instances_filter_status(client: APIClient):
    activation = prepare_init_data()
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

    filter_name = "failed"
    response = client.get(
        f"{api_url_v1}/activation-instances/?status={filter_name}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["name"] == instances[1].name


@pytest.mark.django_db
def test_retrieve_activation_instance(client: APIClient):
    activation = prepare_init_data()
    instance = models.ActivationInstance.objects.create(
        name="activation-instance",
        activation=activation,
    )
    response = client.get(f"{api_url_v1}/activation-instances/{instance.id}/")

    assert response.status_code == status.HTTP_200_OK
    assert_activation_instance_data(response.json(), instance)


@pytest.mark.django_db
def test_retrieve_activation_instance_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/activation-instances/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_list_logs_from_activation_instance(client: APIClient):
    activation = prepare_init_data()
    instance = models.ActivationInstance.objects.create(
        name="test-activation-instance",
        activation=activation,
    )

    models.ActivationInstanceLog.objects.bulk_create(
        [
            models.ActivationInstanceLog(
                log="activation-instance-log-1",
                line_number=1,
                activation_instance=instance,
            ),
            models.ActivationInstanceLog(
                log="activation-instance-log-2",
                line_number=2,
                activation_instance=instance,
            ),
        ]
    )

    response = client.get(
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
        "activation_instance",
    ]


@pytest.mark.django_db
def test_delete_activation_instance(client: APIClient):
    activation = prepare_init_data()
    instance = models.ActivationInstance.objects.create(
        name="activation-instance",
        activation=activation,
    )

    response = client.delete(
        f"{api_url_v1}/activation-instances/{instance.id}/"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert (
        models.ActivationInstance.objects.filter(pk=instance.id).count() == 0
    )


def assert_activation_instance_data(
    data: Dict[str, Any], instance: models.ActivationInstance
):
    assert data == {
        "id": instance.id,
        "name": instance.name,
        "status": str(instance.status),
        "activation_id": instance.activation.id,
        "started_at": instance.started_at.strftime(DATETIME_FORMAT),
        "ended_at": instance.ended_at,
    }


def prepare_init_data():
    rulebook = models.Rulebook.objects.create(
        name="test-rulebook.yml",
        path="rulebooks",
        rulesets=TEST_RULESETS_SAMPLE,
    )
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    activation = models.Activation.objects.create(
        name="test-activation",
        rulebook=rulebook,
        user=user,
    )

    return activation
