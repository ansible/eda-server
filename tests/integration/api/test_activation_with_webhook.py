#  Copyright 2024 Red Hat, Inc.
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
import secrets
import uuid

import pytest
import yaml
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from aap_eda.core.enums import (
    ACTIVATION_STATUS_MESSAGE_MAP,
    ActivationStatus,
    RestartPolicy,
)
from tests.integration.constants import api_url_v1

TEST_EXTRA_VAR = """
---
collections:
  - community.general
  - benthomasson.eda
"""

TEST_ACTIVATION = {
    "name": "test-activation",
    "description": "test activation",
    "is_enabled": True,
    "decision_environment_id": 1,
    "project_id": 1,
    "rulebook_id": 1,
    "extra_var": TEST_EXTRA_VAR,
    "restart_policy": RestartPolicy.ON_FAILURE,
    "restart_count": 0,
    "status_message": "",
}

TEST_AWX_TOKEN = {
    "name": "test-awx-token",
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
  sources:
   - name: demo
     ansible.eda.range:
       limit: 10
     filters:
        - ansible.eda.json_filter:
            include_keys:
              - payload
  rules:
    - name: rule1
      condition: true
      action:
         debug:
"""

LEGACY_TEST_RULESETS = """
---
- name: hello
  hosts: localhost
  gather_facts: false
  sources:
   - ansible.eda.range:
       limit: 10
  rules:
    - name: rule1
      condition: true
      action:
         debug:
"""

PARTIAL_TEST_RULESETS = """
---
- name: hello
  hosts: localhost
  gather_facts: false
  sources:
   - name: demo1
     ansible.eda.range:
       limit: 10
   - name: demo3
     ansible.eda.range:
       limit: 10
  rules:
    - name: rule1
      condition: true
      action:
         debug:
"""


def create_activation_related_data(
    webhook_names, with_project=True, rulesets=TEST_RULESETS
):
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password=secrets.token_hex(32),
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
        secret=secrets.token_hex(32),
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
            description=TEST_RULEBOOK["description"],
            rulesets=rulesets,
            project_id=project_id,
        ).pk
        if with_project
        else None
    )

    webhooks = []
    for name in webhook_names:
        webhook = models.Webhook.objects.create(
            uuid=uuid.uuid4(),
            name=name,
            owner=user,
        )
        webhooks.append(webhook)

    return {
        "user_id": user_id,
        "decision_environment_id": decision_environment_id,
        "project_id": project_id,
        "rulebook_id": rulebook_id,
        "extra_var": TEST_EXTRA_VAR,
        "credential_id": credential_id,
        "webhooks": webhooks,
    }


def create_activation(fks: dict):
    activation_data = TEST_ACTIVATION.copy()
    activation_data["decision_environment_id"] = fks["decision_environment_id"]
    activation_data["project_id"] = fks["project_id"]
    activation_data["rulebook_id"] = fks["rulebook_id"]
    activation_data["user_id"] = fks["user_id"]
    activation = models.Activation(**activation_data)
    activation.save()
    for webhook in fks["webhooks"]:
        activation.webhooks.add(webhook)

    return activation


@pytest.mark.django_db
def test_create_activation_with_webhooks(
    admin_client: APIClient, preseed_credential_types
):
    fks = create_activation_related_data(["demo"])
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["webhooks"] = [webhook.id for webhook in fks["webhooks"]]

    admin_client.post(
        f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN
    )
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.data
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert activation.rulebook_name == TEST_RULEBOOK["name"]
    swapped_ruleset = yaml.safe_load(activation.rulebook_rulesets)
    assert sorted(swapped_ruleset[0]["sources"][0].keys()) == [
        "ansible.eda.pg_listener",
        "filters",
        "name",
    ]
    assert activation.status == ActivationStatus.PENDING
    assert (
        activation.status_message
        == ACTIVATION_STATUS_MESSAGE_MAP[activation.status]
    )
    assert data["webhooks"][0]["name"] == "demo"


@pytest.mark.django_db
def test_list_activations_by_webhook(
    admin_client: APIClient,
    default_activation: models.Activation,
    new_activation: models.Activation,
    default_webhook: models.Webhook,
):
    response = admin_client.get(
        f"{api_url_v1}/webhooks/{default_webhook.id}/activations/"
    )

    data = response.data["results"]

    assert response.status_code == status.HTTP_200_OK
    assert len(data) == 0

    activation_1 = default_activation
    activation_2 = new_activation

    activation_1.webhooks.add(default_webhook)
    activation_2.webhooks.add(default_webhook)

    response = admin_client.get(
        f"{api_url_v1}/webhooks/{default_webhook.id}/activations/"
    )

    data = response.data["results"]

    assert response.status_code == status.HTTP_200_OK
    assert len(data) == 2
    assert sorted([d["name"] for d in data]) == sorted(
        [activation_1.name, activation_2.name]
    )


@pytest.mark.django_db
def test_create_activation_with_bad_webhook(admin_client: APIClient):
    fks = create_activation_related_data(["demo"])
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["webhooks"] = [1492]

    admin_client.post(
        f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN
    )
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        str(response.data["webhooks"][0])
        == "Webhook with id 1492 does not exist"
    )


webhook_src_test_data = [
    (
        ["demo"],
        {},
        LEGACY_TEST_RULESETS,
        status.HTTP_400_BAD_REQUEST,
        (
            "No matching sources found for the following Event stream(s): "
            "demo. None of the sources in the rulebook have name. "
            "Please consider adding name to all the sources in your "
            "rulebook."
        ),
        "webhooks",
    ),
    (
        ["demo"],
        {"swap_single_source": True},
        LEGACY_TEST_RULESETS,
        status.HTTP_201_CREATED,
        "",
        "webhooks",
    ),
    (
        ["demo1", "demo2"],
        {},
        PARTIAL_TEST_RULESETS,
        status.HTTP_400_BAD_REQUEST,
        (
            "No matching sources found for the following Event stream(s): "
            "demo2. The current source names in the rulebook are: "
            "demo1, demo3."
        ),
        "webhooks",
    ),
    (
        ["demo1", "demo2"],
        {"swap_single_source": True},
        LEGACY_TEST_RULESETS,
        status.HTTP_400_BAD_REQUEST,
        (
            "You have more than 1 event stream attached to the rulebook, "
            "whilst there is only source in the rulebook."
        ),
        "webhooks",
    ),
    (
        ["demo11", "demo21"],
        {},
        PARTIAL_TEST_RULESETS,
        status.HTTP_400_BAD_REQUEST,
        (
            "No matching sources found for the following Event stream(s): "
            "demo11, demo21. The current source names in the "
            "rulebook are: demo1, demo3."
        ),
        "webhooks",
    ),
    (
        ["demo1"],
        {"swap_single_source": True},
        PARTIAL_TEST_RULESETS,
        status.HTTP_400_BAD_REQUEST,
        (
            "You have more than 1 source in the rulebook. Please add "
            "name to your sources and disable this option."
        ),
        "swap_single_source",
    ),
]


@pytest.mark.parametrize(
    "webhook_names, extra_args, rulesets, status_code, message, error_key",
    webhook_src_test_data,
)
@pytest.mark.django_db
def test_bad_src_activation_with_webhooks(
    admin_client: APIClient,
    preseed_credential_types,
    webhook_names,
    extra_args,
    rulesets,
    status_code,
    message,
    error_key,
):
    fks = create_activation_related_data(webhook_names, True, rulesets)
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["webhooks"] = [webhook.id for webhook in fks["webhooks"]]
    for key, value in extra_args.items():
        test_activation[key] = value

    admin_client.post(
        f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN
    )
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status_code
    if message:
        assert response.json()[error_key][0] == message
