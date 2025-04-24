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

# TODO(doston): this entire test module needs to be updated to use fixtures

import pytest
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import enums, models
from tests.integration.constants import api_url_v1

TEST_ACTIVATION_DATA = {
    "name": "test-activation",
    "description": "test activation",
    "is_enabled": True,
    "restart_policy": enums.RestartPolicy.ON_FAILURE,
    "restart_count": 0,
    "status_message": "",
    "log_level": enums.RulebookProcessLogLevel.DEBUG,
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


def create_activation_related_data():
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    organization = models.Organization.objects.get_or_create(
        name=settings.DEFAULT_ORGANIZATION_NAME,
        description="The default organization",
    )[0]
    decision_environment = models.DecisionEnvironment.objects.create(
        name="test-de",
        image_url="quay.io/ansible/ansible-rulebook",
        description="test DecisionEnvironment",
        organization=organization,
    )
    project = models.Project.objects.create(
        git_hash="684f62df18ce5f8d5c428e53203b9b975426eed0",
        name="test_project",
        description="test project",
        url="https://git.example.com/acme/project-01",
        organization=organization,
    )
    rulebook = models.Rulebook.objects.create(
        name="test_rulebook.yaml",
        rulesets=TEST_RULESETS,
        description="test rulebook",
        project_id=project.id,
        organization=organization,
    )

    return {
        "user_id": user.id,
        "decision_environment_id": decision_environment.id,
        "project_id": project.id,
        "rulebook_id": rulebook.id,
        "organization_id": organization.id,
    }


@pytest.fixture(autouse=True)
def use_k8s_setting(settings):
    settings.DEPLOYMENT_TYPE = "k8s"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("activation_name", "service_name", "status_code", "key"),
    [
        (
            "valid-activation-name",
            "valid-service-name",
            status.HTTP_201_CREATED,
            None,
        ),
        (
            "invalid_activation_name",
            "valid-service-name",
            status.HTTP_201_CREATED,
            None,
        ),
        (
            "valid-activation-name",
            "invalid_service_name",
            status.HTTP_400_BAD_REQUEST,
            "k8s_service_name",
        ),
        (
            "invalid_activation_name",
            "invalid_service_name",
            status.HTTP_400_BAD_REQUEST,
            "k8s_service_name",
        ),
        ("valid-activation-name", None, status.HTTP_201_CREATED, None),
        (
            "convertable_invalid_activation_name",
            None,
            status.HTTP_201_CREATED,
            None,
        ),
    ],
)
def test_create_k8s_activation_with_service_name(
    admin_client: APIClient,
    preseed_credential_types,
    activation_name,
    service_name,
    status_code,
    key,
):
    fks = create_activation_related_data()
    test_activation = TEST_ACTIVATION_DATA.copy()
    test_activation["name"] = activation_name
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["project_id"] = fks["project_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["organization_id"] = fks["organization_id"]
    test_activation["k8s_service_name"] = service_name

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status_code

    if response.status_code == status.HTTP_201_CREATED:
        activation = models.Activation.objects.get(id=response.data["id"])

        if service_name and service_name.startswith("valid"):
            assert activation.k8s_service_name == service_name
        else:
            assert activation.k8s_service_name == activation_name.replace(
                "_", "-"
            )
    else:
        if service_name:
            assert (
                f"{service_name} must be a valid RFC 1035 label name"
                in response.data[key]
            )
        else:
            assert (
                "Please provide a name, that's a valid RFC 1035 name, "
                "couldn't auto generate a service name"
            ) in response.data[key]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "activation_name",
    ["valid-activation-name", "invalid_activation_name"],
)
def test_create_podman_activation(
    admin_client: APIClient,
    preseed_credential_types,
    activation_name,
    settings,
):
    settings.DEPLOYMENT_TYPE = "podman"
    fks = create_activation_related_data()
    test_activation = TEST_ACTIVATION_DATA.copy()
    test_activation["name"] = activation_name
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["project_id"] = fks["project_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["organization_id"] = fks["organization_id"]

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status.HTTP_201_CREATED
    activation = models.Activation.objects.get(id=response.data["id"])
    assert activation.k8s_service_name is None


@pytest.mark.django_db
def test_get_activations_with_service_name(
    admin_client: APIClient,
    preseed_credential_types,
):
    activation_name = "test-activation"
    fks = create_activation_related_data()
    test_activation = TEST_ACTIVATION_DATA.copy()
    test_activation["name"] = activation_name
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["project_id"] = fks["project_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["organization_id"] = fks["organization_id"]

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status.HTTP_201_CREATED

    activation_id = response.data["id"]
    response = admin_client.get(f"{api_url_v1}/activations/{activation_id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["k8s_service_name"] == activation_name

    response = admin_client.get(f"{api_url_v1}/activations/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["results"][0]["k8s_service_name"] == activation_name
