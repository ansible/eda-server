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

# TODO(doston): this entire test module needs to be updated to use fixtures

import secrets
import uuid

import pytest
import yaml
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.api.constants import SOURCE_MAPPING_ERROR_KEY
from aap_eda.core import enums, models
from aap_eda.core.enums import (
    ACTIVATION_STATUS_MESSAGE_MAP,
    ActivationStatus,
    RestartPolicy,
)
from aap_eda.core.utils.credentials import inputs_to_store
from aap_eda.core.utils.rulebook import (
    DEFAULT_SOURCE_NAME_PREFIX,
    get_rulebook_hash,
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

LEGACY_TEST_RULESETS_MULTIPLE_SOURCES = """
---
- name: hello
  hosts: localhost
  sources:
   - ansible.eda.range:
       limit: 10
   - ansible.eda.range:
       limit: 10
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


def custom_credential(
    name: str, organization: models.Organization
) -> models.EdaCredential:
    ctype = models.CredentialType.objects.create(
        name=name,
        inputs={
            "fields": [
                {"id": "username"},
                {"id": "password"},
            ]
        },
        injectors={
            "extra_vars": {
                "custom_username": "{{ username }}",
                "custom_password": "{{ password }}",
            }
        },
    )
    return models.EdaCredential.objects.create(
        name=name,
        description="Default Credential",
        credential_type=ctype,
        inputs=inputs_to_store(
            {"username": f"{name}-user", "password": "dummy-password"}
        ),
        organization=organization,
    )


def create_activation_related_data(
    event_stream_names, with_project=True, rulesets=TEST_RULESETS, appendix=""
):
    user = models.User.objects.create_user(
        username="luke.skywalker" + appendix,
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password=secrets.token_hex(32),
    )
    user_id = user.pk
    models.AwxToken.objects.create(
        name=TEST_AWX_TOKEN["name"] + appendix,
        token=TEST_AWX_TOKEN["token"] + appendix,
        user=user,
    )
    organization = models.Organization.objects.get_or_create(
        name=settings.DEFAULT_ORGANIZATION_NAME,
        description="The default organization",
    )[0]
    registry_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    credential_id = models.EdaCredential.objects.create(
        name="eda-credential" + appendix,
        description="Default Registry Credential",
        credential_type=registry_credential_type,
        inputs=inputs_to_store(
            {
                "username": "dummy-user" + appendix,
                "password": "dummy-password" + appendix,
                "host": "quay.io",
            }
        ),
        organization=organization,
    ).pk
    decision_environment_id = models.DecisionEnvironment.objects.create(
        name=TEST_DECISION_ENV["name"] + appendix,
        image_url=TEST_DECISION_ENV["image_url"],
        description=TEST_DECISION_ENV["description"],
        eda_credential_id=credential_id,
        organization=organization,
    ).pk
    project_id = (
        models.Project.objects.create(
            git_hash=TEST_PROJECT["git_hash"] + appendix,
            name=TEST_PROJECT["name"] + appendix,
            url=TEST_PROJECT["url"],
            description=TEST_PROJECT["description"],
            organization=organization,
        ).pk
        if with_project
        else None
    )
    rulebook_id = (
        models.Rulebook.objects.create(
            name=TEST_RULEBOOK["name"] + appendix,
            description=TEST_RULEBOOK["description"],
            rulesets=rulesets,
            project_id=project_id,
            organization=organization,
        ).pk
        if with_project
        else None
    )

    hmac_credential_type = models.CredentialType.objects.get(
        name=enums.EventStreamCredentialType.HMAC
    )
    hmac_credential_id = models.EdaCredential.objects.create(
        name="default-hmac-credential" + appendix,
        description="Default HMAC Credential",
        credential_type=hmac_credential_type,
        inputs=inputs_to_store(
            {
                "auth_type": "hmac",
                "hmac_algorithm": "sha256",
                "secret": "secret" + appendix,
                "header_key": "X-Hub-Signature-256",
                "hmac_format": "hex",
                "hmac_signature_prefix": "sha256=",
            }
        ),
        organization=organization,
    ).id

    event_streams = []
    for name in event_stream_names:
        event_stream = models.EventStream.objects.create(
            uuid=uuid.uuid4(),
            name=name,
            owner=user,
            organization=organization,
            eda_credential_id=hmac_credential_id,
        )
        event_streams.append(event_stream)

    return {
        "user_id": user_id,
        "decision_environment_id": decision_environment_id,
        "project_id": project_id,
        "rulebook_id": rulebook_id,
        "extra_var": TEST_EXTRA_VAR,
        "credential_id": credential_id,
        "event_streams": event_streams,
        "organization_id": organization.id,
    }


def create_activation(fks: dict):
    activation_data = TEST_ACTIVATION.copy()
    activation_data["decision_environment_id"] = fks["decision_environment_id"]
    activation_data["project_id"] = fks["project_id"]
    activation_data["rulebook_id"] = fks["rulebook_id"]
    activation_data["user_id"] = fks["user_id"]
    activation_data["organization_id"] = fks["organization_id"]
    activation = models.Activation(**activation_data)
    activation.save()
    for event_stream in fks["event_streams"]:
        activation.event_streams.add(event_stream)

    return activation


@pytest.mark.django_db
def test_create_activation_with_event_stream(
    admin_client: APIClient, preseed_credential_types
):
    fks = create_activation_related_data(["demo"])
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["organization_id"] = fks["organization_id"]
    source_mappings = []
    for event_stream in fks["event_streams"]:
        source_mappings.append(
            {
                "event_stream_name": event_stream.name,
                "event_stream_id": event_stream.id,
                "rulebook_hash": get_rulebook_hash(TEST_RULESETS),
                "source_name": "demo",
            }
        )
    test_activation["source_mappings"] = yaml.dump(source_mappings)

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
    assert data["event_streams"][0]["name"] == "demo"


@pytest.mark.django_db
def test_list_activations_by_event_stream(
    admin_client: APIClient,
    default_activation: models.Activation,
    new_activation: models.Activation,
    default_event_stream: models.EventStream,
):
    response = admin_client.get(
        f"{api_url_v1}/event-streams/{default_event_stream.id}/activations/"
    )

    data = response.data["results"]

    assert response.status_code == status.HTTP_200_OK
    assert len(data) == 0

    activation_1 = default_activation
    activation_2 = new_activation

    activation_1.event_streams.add(default_event_stream)
    activation_2.event_streams.add(default_event_stream)

    response = admin_client.get(
        f"{api_url_v1}/event-streams/{default_event_stream.id}/activations/"
    )

    data = response.data["results"]

    assert response.status_code == status.HTTP_200_OK
    assert len(data) == 2
    assert sorted([d["name"] for d in data]) == sorted(
        [activation_1.name, activation_2.name]
    )


@pytest.mark.django_db
def test_create_activation_with_bad_format_in_mappings(
    admin_client: APIClient, preseed_credential_types
):
    fks = create_activation_related_data(["demo"])
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["organization_id"] = fks["organization_id"]
    test_activation["source_mappings"] = "bad_format"

    admin_client.post(
        f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN
    )
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert str(response.data[SOURCE_MAPPING_ERROR_KEY][0]) == (
        "Input source mappings should be a list of mappings"
    )


@pytest.mark.django_db
def test_create_activation_with_corrupted_mappings(
    admin_client: APIClient, preseed_credential_types
):
    fks = create_activation_related_data(["demo"])
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["organization_id"] = fks["organization_id"]
    test_activation["source_mappings"] = "corrupted\n  key: value\n"

    admin_client.post(
        f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN
    )
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Faild to parse source mappings: " in str(
        response.data[SOURCE_MAPPING_ERROR_KEY][0]
    )


@pytest.mark.django_db
def test_create_activation_with_missing_keys_in_mappings(
    admin_client: APIClient, preseed_credential_types
):
    fks = create_activation_related_data(["demo"])
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["organization_id"] = fks["organization_id"]
    source_mappings = [
        {
            "event_stream_name": "fake",
            "source_name": "demo",
        }
    ]
    test_activation["source_mappings"] = yaml.dump(source_mappings)

    admin_client.post(
        f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN
    )
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert str(response.data[SOURCE_MAPPING_ERROR_KEY][0]) == (
        "The source mapping {'event_stream_name': 'fake', "
        "'source_name': 'demo'} is missing the required keys: "
        "['event_stream_id', 'rulebook_hash']"
    )


@pytest.mark.django_db
def test_create_activation_with_bad_event_stream(
    admin_client: APIClient, preseed_credential_types
):
    fks = create_activation_related_data(["demo"])
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["organization_id"] = fks["organization_id"]
    source_mappings = [
        {
            "event_stream_name": "fake",
            "event_stream_id": 1492,
            "rulebook_hash": get_rulebook_hash(TEST_RULESETS),
            "source_name": "demo",
        }
    ]
    test_activation["source_mappings"] = yaml.dump(source_mappings)

    admin_client.post(
        f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN
    )
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        str(response.data[SOURCE_MAPPING_ERROR_KEY][0])
        == "Event stream id 1492 not found"
    )


@pytest.mark.django_db
def test_create_activation_with_bad_event_stream_name(
    admin_client: APIClient, preseed_credential_types
):
    fks = create_activation_related_data(["demo"])
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["organization_id"] = fks["organization_id"]
    source_mappings = [
        {
            "event_stream_name": "missing_name",
            "event_stream_id": fks["event_streams"][0].id,
            "rulebook_hash": get_rulebook_hash(TEST_RULESETS),
            "source_name": "demo",
        }
    ]
    test_activation["source_mappings"] = yaml.dump(source_mappings)

    admin_client.post(
        f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN
    )
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        str(response.data[SOURCE_MAPPING_ERROR_KEY][0])
        == "Event stream missing_name did not match with name demo in database"
    )


@pytest.mark.django_db
def test_create_activation_with_bad_rulebook_hash(
    admin_client: APIClient, preseed_credential_types
):
    fks = create_activation_related_data(["demo"])
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["organization_id"] = fks["organization_id"]
    source_mappings = [
        {
            "event_stream_name": fks["event_streams"][0].name,
            "event_stream_id": fks["event_streams"][0].id,
            "rulebook_hash": "abdd",
            "source_name": "demo",
        }
    ]
    test_activation["source_mappings"] = yaml.dump(source_mappings)

    admin_client.post(
        f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN
    )
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert str(response.data[SOURCE_MAPPING_ERROR_KEY][0]) == (
        "Rulebook has changed since the sources were mapped."
        " Please reattach Event streams again"
    )


@pytest.mark.django_db
def test_create_activation_with_duplicate_source_name(
    admin_client: APIClient, preseed_credential_types
):
    fks = create_activation_related_data(
        ["demo"], rulesets=LEGACY_TEST_RULESETS_MULTIPLE_SOURCES
    )
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["organization_id"] = fks["organization_id"]
    source_mappings = [
        {
            "event_stream_name": fks["event_streams"][0].name,
            "event_stream_id": fks["event_streams"][0].id,
            "rulebook_hash": "abdd",
            "source_name": "demo",
        },
        {
            "event_stream_name": f"{fks['event_streams'][0].name}_1",
            "event_stream_id": fks["event_streams"][0].id,
            "rulebook_hash": get_rulebook_hash(
                LEGACY_TEST_RULESETS_MULTIPLE_SOURCES
            ),
            "source_name": "demo",
        },
    ]
    test_activation["source_mappings"] = yaml.dump(source_mappings)

    admin_client.post(
        f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN
    )
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "The following sources demo are being used multiple times"
        == response.data[SOURCE_MAPPING_ERROR_KEY][0]
    )


@pytest.mark.django_db
def test_create_activation_with_duplicate_event_stream_name(
    admin_client: APIClient, preseed_credential_types
):
    fks = create_activation_related_data(
        ["demo"], rulesets=LEGACY_TEST_RULESETS_MULTIPLE_SOURCES
    )
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["organization_id"] = fks["organization_id"]
    source_mappings = [
        {
            "event_stream_name": fks["event_streams"][0].name,
            "event_stream_id": fks["event_streams"][0].id,
            "rulebook_hash": "abdd",
            "source_name": "demo",
        },
        {
            "event_stream_name": fks["event_streams"][0].name,
            "event_stream_id": fks["event_streams"][0].id,
            "rulebook_hash": get_rulebook_hash(
                LEGACY_TEST_RULESETS_MULTIPLE_SOURCES
            ),
            "source_name": "demo1",
        },
    ]
    test_activation["source_mappings"] = yaml.dump(source_mappings)

    admin_client.post(
        f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN
    )
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "The following event streams demo are being used multiple times"
        == response.data[SOURCE_MAPPING_ERROR_KEY][0]
    )


event_stream_src_test_data = [
    (
        [("missing_source", "demo")],
        LEGACY_TEST_RULESETS,
        status.HTTP_400_BAD_REQUEST,
        "The source missing_source does not exist",
        SOURCE_MAPPING_ERROR_KEY,
    ),
    (
        [(f"{DEFAULT_SOURCE_NAME_PREFIX}1", "demo")],
        LEGACY_TEST_RULESETS,
        status.HTTP_201_CREATED,
        "",
        SOURCE_MAPPING_ERROR_KEY,
    ),
    (
        [("demo1", "demo1"), ("demo2", "demo3")],
        PARTIAL_TEST_RULESETS,
        status.HTTP_400_BAD_REQUEST,
        "The source demo2 does not exist",
        SOURCE_MAPPING_ERROR_KEY,
    ),
    (
        [
            (f"{DEFAULT_SOURCE_NAME_PREFIX}1", "demo1"),
            (f"{DEFAULT_SOURCE_NAME_PREFIX}2", "demo2"),
        ],
        LEGACY_TEST_RULESETS,
        status.HTTP_400_BAD_REQUEST,
        "The rulebook has 1 source(s) while you have provided 2 event streams",
        SOURCE_MAPPING_ERROR_KEY,
    ),
    (
        [("demo11", "demo1"), ("demo21", "demo3")],
        PARTIAL_TEST_RULESETS,
        status.HTTP_400_BAD_REQUEST,
        "The source demo11 does not exist",
        SOURCE_MAPPING_ERROR_KEY,
    ),
    (
        [(f"{DEFAULT_SOURCE_NAME_PREFIX}3", "demo1")],
        LEGACY_TEST_RULESETS_MULTIPLE_SOURCES,
        status.HTTP_201_CREATED,
        "",
        SOURCE_MAPPING_ERROR_KEY,
    ),
]


@pytest.mark.parametrize(
    "source_tuples, rulesets, status_code, message, error_key",
    event_stream_src_test_data,
)
@pytest.mark.django_db
def test_bad_src_activation_with_event_stream(
    admin_client: APIClient,
    preseed_credential_types,
    source_tuples,
    rulesets,
    status_code,
    message,
    error_key,
):
    names = [event_stream_name for _, event_stream_name in source_tuples]
    fks = create_activation_related_data(names, True, rulesets)
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["organization_id"] = fks["organization_id"]

    source_mappings = []

    for src, event_source_name in source_tuples:
        event_stream = models.EventStream.objects.get(name=event_source_name)
        source_mappings.append(
            {
                "source_name": src,
                "rulebook_hash": get_rulebook_hash(rulesets),
                "event_stream_name": event_stream.name,
                "event_stream_id": event_stream.id,
            }
        )
    test_activation["source_mappings"] = yaml.dump(source_mappings)

    admin_client.post(
        f"{api_url_v1}/users/me/awx-tokens/", data=TEST_AWX_TOKEN
    )
    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status_code
    if message:
        assert response.json()[error_key][0] == message


@pytest.mark.django_db
def test_update_activation_with_everything(
    admin_client: APIClient, preseed_credential_types
):
    fks = create_activation_related_data(["demo"], rulesets=TEST_RULESETS)
    organization = models.Organization.objects.get(pk=fks["organization_id"])
    credential = custom_credential("test", organization)

    test_activation = {
        "name": "test-activation",
        "description": "test activation",
        "is_enabled": False,
        "extra_var": TEST_EXTRA_VAR,
        "eda_credentials": [credential.id],
        "decision_environment_id": fks["decision_environment_id"],
        "rulebook_id": fks["rulebook_id"],
        "organization_id": fks["organization_id"],
        "skip_audit_events": False,
        "restart_policy": enums.RestartPolicy.ALWAYS,
        "log_level": enums.RulebookProcessLogLevel.ERROR,
        "k8s_service_name": "demo-service",
    }
    source_mappings = []
    for event_stream in fks["event_streams"]:
        source_mappings.append(
            {
                "event_stream_name": event_stream.name,
                "event_stream_id": event_stream.id,
                "rulebook_hash": get_rulebook_hash(TEST_RULESETS),
                "source_name": "demo",
            }
        )
    test_activation["source_mappings"] = yaml.dump(source_mappings)

    response = admin_client.post(
        f"{api_url_v1}/activations/", data=test_activation
    )
    assert response.status_code == status.HTTP_201_CREATED
    activation_id = response.data["id"]

    fks2 = create_activation_related_data(
        ["demo-2"], rulesets=LEGACY_TEST_RULESETS, appendix="2"
    )
    credential2 = custom_credential("test-2", organization)
    extra_var2 = TEST_EXTRA_VAR.replace(
        "community.general", "community.shared"
    )

    test_activation2 = {
        "name": "test-activation-2",
        "description": "test activation 2",
        "extra_var": extra_var2,
        "eda_credentials": [credential2.id],
        "decision_environment_id": fks2["decision_environment_id"],
        "rulebook_id": fks2["rulebook_id"],
        "skip_audit_events": True,
        "restart_policy": enums.RestartPolicy.ON_FAILURE,
        "log_level": enums.RulebookProcessLogLevel.INFO,
        "k8s_service_name": "demo-service-2",
    }
    source_mappings2 = []
    for event_stream in fks2["event_streams"]:
        source_mappings2.append(
            {
                "event_stream_name": event_stream.name,
                "event_stream_id": event_stream.id,
                "rulebook_hash": get_rulebook_hash(LEGACY_TEST_RULESETS),
                "source_name": f"{DEFAULT_SOURCE_NAME_PREFIX}1",
            }
        )
    # to be enabled in another PR
    # test_activation2["source_mappings"] = yaml.dump(source_mappings2)
    response = admin_client.patch(
        f"{api_url_v1}/activations/{activation_id}/", data=test_activation2
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.data
    activation = models.Activation.objects.filter(id=data["id"]).first()
    assert activation.rulebook_name == f"{TEST_RULEBOOK['name']}2"
    # swapped_ruleset = yaml.safe_load(activation.rulebook_rulesets)
    # assert sorted(swapped_ruleset[0]["sources"][0].keys()) == [
    #    "ansible.eda.pg_listener",
    #    "name",
    # ]
    # assert data["event_streams"][0]["name"] == "demo-2"
    for key, val in test_activation2.items():
        if key == "extra_var":
            assert activation.extra_var == (
                "collections:\n- community.shared\n- benthomasson.eda\n"
                "custom_password: dummy-password\n"
                "custom_username: test-2-user\n"
            )
            continue
        if key == "eda_credentials":
            assert activation.eda_credentials.all()[0].id == val[0]
            continue
        if key == "source_mappings":
            assert activation.source_mappings.strip() == val.strip()
            continue
        assert getattr(activation, key) == val
