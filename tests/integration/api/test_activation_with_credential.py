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
import pytest
import yaml
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.api.constants import EDA_SERVER_VAULT_LABEL
from aap_eda.api.serializers.activation import is_activation_valid
from aap_eda.core import models
from aap_eda.core.enums import DefaultCredentialType, RestartPolicy
from aap_eda.core.utils.crypto.base import SecretValue
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
    "log_level": "debug",
}

PROJECT_GIT_HASH = "684f62df18ce5f8d5c428e53203b9b975426eed0"

TEST_PROJECT = {
    "git_hash": PROJECT_GIT_HASH,
    "name": "test-project-01",
    "url": "https://git.example.com/acme/project-01",
    "description": "test project",
}

TEST_AWX_TOKEN = {
    "name": "test-awx-token",
    "description": "test AWX token",
    "token": "abc123xyx",
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
var_1: demo
var_2: test
"""

OVERLAP_EXTRA_VAR = """
---
sasl_plain_username: demo
sasl_plain_password: secret
"""

RULESET_WITH_JOB_TEMPLATE = """
---
- name: test
  sources:
    - ansible.eda.range:
        limit: 10
  rules:
    - name: example rule
      condition: event.i == 8
      actions:
        - run_job_template:
            organization: Default
            name: example
"""

KAFKA_INPUTS = {
    "fields": [
        {"id": "certfile", "type": "string", "label": "Certificate File"},
        {
            "id": "keyfile",
            "type": "string",
            "label": "Key File",
            "secret": True,
        },
        {"id": "password", "type": "string", "label": "Password"},
        {
            "id": "sasl_username",
            "type": "string",
            "label": "SASL User Name",
        },
        {
            "id": "sasl_password",
            "type": "string",
            "label": "SASL Password",
            "secret": True,
        },
    ]
}


INJECTORS = {
    "extra_vars": {
        "keyfile": "{{ keyfile |default(None)}}",
        "certfile": "{{ certfile|default(None) }}",
        "password": "{{ password |default(None)}}",
        "sasl_plain_password": "{{ sasl_password |default(None)}}",
        "sasl_plain_username": "{{ sasl_username |default(None)}}",
    }
}


@pytest.fixture
def kafka_credential_type() -> models.CredentialType:
    return models.CredentialType.objects.create(
        name="type1", inputs=KAFKA_INPUTS, injectors=INJECTORS
    )


def create_user_credential_type() -> models.CredentialType:
    return models.CredentialType.objects.create(
        name="user_type",
        inputs={
            "fields": [
                {"id": "sasl_username"},
                {"id": "sasl_password"},
            ]
        },
        injectors={
            "extra_vars": {
                "sasl_username": "{{ sasl_username }}",
                "sasl_password": "{{ sasl_password }}",
            }
        },
    )


def create_activation_related_data(extra_var, with_project=True):
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    user_id = user.pk
    awx_token = models.AwxToken.objects.create(
        name=TEST_AWX_TOKEN["name"],
        token=TEST_AWX_TOKEN["token"],
        user=user,
    )
    awx_token_id = awx_token.id

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
            project_id=project_id,
        ).pk
        if with_project
        else None
    )

    run_job_rulebook_id = (
        models.Rulebook.objects.create(
            name="test rulebook",
            rulesets=RULESET_WITH_JOB_TEMPLATE,
            project_id=project_id,
        ).pk
        if with_project
        else None
    )
    extra_var_id = models.ExtraVar.objects.create(extra_var=extra_var).pk

    return {
        "user_id": user_id,
        "awx_token_id": awx_token_id,
        "decision_environment_id": decision_environment_id,
        "project_id": project_id,
        "rulebook_id": rulebook_id,
        "run_job_rulebook_id": run_job_rulebook_id,
        "extra_var_id": extra_var_id,
    }


@pytest.mark.django_db
def test_is_activation_valid_with_token_and_run_job_template(
    client: APIClient,
    preseed_credential_types,
):
    fks = create_activation_related_data(TEST_EXTRA_VAR)

    activation = models.Activation.objects.create(
        name="test",
        description="test activation",
        rulebook_id=fks["run_job_rulebook_id"],
        decision_environment_id=fks["decision_environment_id"],
        project_id=fks["project_id"],
        awx_token_id=fks["awx_token_id"],
        user_id=fks["user_id"],
    )

    valid, _ = is_activation_valid(activation)
    assert valid is True


@pytest.mark.django_db
def test_is_activation_valid_with_aap_credential_and_run_job_template(
    client: APIClient,
    preseed_credential_types,
):
    fks = create_activation_related_data(TEST_EXTRA_VAR)
    aap_credential_type = models.CredentialType.objects.get(
        name=DefaultCredentialType.AAP,
    )
    credential = models.EdaCredential.objects.create(
        name="test_eda_credential",
        inputs={"username": "adam", "password": "secret"},
        managed=False,
        credential_type_id=aap_credential_type.id,
    )

    activation = models.Activation.objects.create(
        name="test",
        description="test activation",
        rulebook_id=fks["run_job_rulebook_id"],
        decision_environment_id=fks["decision_environment_id"],
        project_id=fks["project_id"],
        awx_token_id=fks["awx_token_id"],
        user_id=fks["user_id"],
    )
    activation.eda_credentials.add(credential)

    valid, _ = is_activation_valid(activation)
    assert valid is True


@pytest.mark.django_db
def test_is_activation_valid_with_run_job_template_and_no_token_no_credential(
    client: APIClient,
    preseed_credential_types,
):
    fks = create_activation_related_data(TEST_EXTRA_VAR)

    activation = models.Activation.objects.create(
        name="test",
        description="test activation",
        rulebook_id=fks["run_job_rulebook_id"],
        decision_environment_id=fks["decision_environment_id"],
        project_id=fks["project_id"],
        user_id=fks["user_id"],
    )

    valid, message = is_activation_valid(activation)

    assert valid is False
    assert (
        "The rulebook requires an Awx Token or " "RH AAP credential."
    ) in message


@pytest.mark.django_db
def test_create_activation_with_eda_credential(
    client: APIClient,
    kafka_credential_type: models.CredentialType,
    preseed_credential_types,
):
    fks = create_activation_related_data(TEST_EXTRA_VAR)
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["extra_var_id"] = fks["extra_var_id"]

    test_eda_credential = {
        "name": "eda-credential",
        "inputs": {"sasl_username": "adam", "sasl_password": "secret"},
        "credential_type_id": kafka_credential_type.id,
    }
    response = client.post(
        f"{api_url_v1}/eda-credentials/", data=test_eda_credential
    )
    test_activation["eda_credentials"] = [response.data["id"]]

    response = client.post(f"{api_url_v1}/activations/", data=test_activation)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.data

    assert data["eda_credentials"][0]["credential_type"] == {
        "id": kafka_credential_type.id,
        "name": kafka_credential_type.name,
        "namespace": None,
        "kind": "cloud",
    }
    activation = models.Activation.objects.filter(id=data["id"]).first()

    assert activation.eda_system_vault_credential is not None
    assert activation.eda_system_vault_credential.name.startswith(
        EDA_SERVER_VAULT_LABEL
    )
    assert activation.eda_system_vault_credential.managed is True
    assert isinstance(
        activation.eda_system_vault_credential.inputs, SecretValue
    )

    assert activation.eda_system_vault_credential.credential_type is not None
    credential_type = activation.eda_system_vault_credential.credential_type
    assert credential_type.name == DefaultCredentialType.VAULT


@pytest.mark.django_db
def test_create_activation_with_key_conflict(
    client: APIClient,
    kafka_credential_type: models.CredentialType,
    preseed_credential_types,
):
    fks = create_activation_related_data(OVERLAP_EXTRA_VAR)
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["extra_var_id"] = fks["extra_var_id"]

    test_eda_credential = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs={"sasl_username": "adam", "sasl_password": "secret"},
        credential_type_id=kafka_credential_type.id,
    )
    test_activation["eda_credentials"] = [test_eda_credential.id]

    response = client.post(f"{api_url_v1}/activations/", data=test_activation)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "Key: sasl_plain_password already exists "
        "in extra var. It conflicts with credential type: type1. "
        "Please check injectors." in response.data["non_field_errors"]
    )


@pytest.mark.django_db
def test_create_activation_with_conflict_credentials(
    client: APIClient,
    preseed_credential_types,
):
    fks = create_activation_related_data(OVERLAP_EXTRA_VAR)
    test_activation = TEST_ACTIVATION.copy()
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    test_activation["extra_var_id"] = fks["extra_var_id"]
    user_credential_type = create_user_credential_type()

    eda_credentials = models.EdaCredential.objects.bulk_create(
        [
            models.EdaCredential(
                name="credential-1",
                inputs={"sasl_username": "adam", "sasl_password": "secret"},
                credential_type_id=user_credential_type.id,
            ),
            models.EdaCredential(
                name="credential-2",
                inputs={"sasl_username": "bearny", "sasl_password": "demo"},
                credential_type_id=user_credential_type.id,
            ),
        ]
    )

    eda_credential_ids = [credential.id for credential in eda_credentials]
    test_activation["eda_credentials"] = eda_credential_ids

    response = client.post(f"{api_url_v1}/activations/", data=test_activation)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "Key: sasl_password already exists "
        "in extra var. It conflicts with credential type: user_type. "
        "Please check injectors." in response.data["non_field_errors"]
    )


@pytest.mark.django_db
def test_create_activation_without_extra_vars_single_credential(
    client: APIClient,
    preseed_credential_types,
):
    fks = create_activation_related_data(OVERLAP_EXTRA_VAR)
    test_activation = TEST_ACTIVATION.copy()
    test_activation.pop("extra_var_id")
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    user_credential_type = create_user_credential_type()

    eda_credential = models.EdaCredential.objects.create(
        name="credential-1",
        inputs={"sasl_username": "adam", "sasl_password": "secret"},
        credential_type_id=user_credential_type.id,
    )

    eda_credential_ids = [eda_credential.id]
    test_activation["eda_credentials"] = eda_credential_ids

    assert models.ExtraVar.objects.count() == 1
    response = client.post(f"{api_url_v1}/activations/", data=test_activation)
    assert response.status_code == status.HTTP_201_CREATED
    assert models.ExtraVar.objects.count() == 2
    extra_var = yaml.safe_load(models.ExtraVar.objects.last().extra_var)
    assert extra_var["sasl_username"] == "adam"
    assert extra_var["sasl_password"] == "secret"


@pytest.mark.django_db
def test_create_activation_without_extra_vars_duplicate_credentials(
    client: APIClient,
    preseed_credential_types,
):
    fks = create_activation_related_data(OVERLAP_EXTRA_VAR)
    test_activation = TEST_ACTIVATION.copy()
    test_activation.pop("extra_var_id")
    test_activation["decision_environment_id"] = fks["decision_environment_id"]
    test_activation["rulebook_id"] = fks["rulebook_id"]
    user_credential_type = create_user_credential_type()

    eda_credentials = models.EdaCredential.objects.bulk_create(
        [
            models.EdaCredential(
                name="credential-1",
                inputs={"sasl_username": "adam", "sasl_password": "secret"},
                credential_type_id=user_credential_type.id,
            ),
            models.EdaCredential(
                name="credential-2",
                inputs={"sasl_username": "bearny", "sasl_password": "demo"},
                credential_type_id=user_credential_type.id,
            ),
        ]
    )

    eda_credential_ids = [credential.id for credential in eda_credentials]
    test_activation["eda_credentials"] = eda_credential_ids

    response = client.post(f"{api_url_v1}/activations/", data=test_activation)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "Key: sasl_password already exists in extra var. It conflicts with"
        " credential type: user_type. Please check injectors."
        in response.data["non_field_errors"]
    )
