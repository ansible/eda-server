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
from unittest import mock

import pytest

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.services.validation import validate_activation

TEST_RULESETS = """
---
- name: hello
  hosts: localhost
  sources:
    - ansible.eda.webhook:
        host: 0.0.0.0
        port: 5000
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


@dataclass
class InitData:
    activation: models.Activation
    decision_environment: models.DecisionEnvironment
    rulebook: models.Rulebook
    extra_var: models.ExtraVar
    user: models.User


@pytest.fixture()
def init_data():
    credential = models.Credential.objects.create(
        name="credential1", username="me", secret="sec1"
    )
    decision_environment = models.DecisionEnvironment.objects.create(
        name="de_test_name",
        image_url="de_test_image_url",
        description="de_test_description",
        credential=credential,
    )
    rulebook = models.Rulebook.objects.create(
        name="rulebook_test_name",
        rulesets=TEST_RULESETS,
        description="rulebook_test_description",
    )
    extra_var = models.ExtraVar.objects.create(
        name="test-extra-var.yml", extra_var=TEST_EXTRA_VAR
    )
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    activation = models.Activation.objects.create(
        decision_environment=decision_environment,
        rulebook_rulesets=TEST_RULESETS,
        rulebook=rulebook,
        extra_var=extra_var,
        user=user,
    )

    return InitData(
        activation=activation,
        decision_environment=decision_environment,
        rulebook=rulebook,
        extra_var=extra_var,
        user=user,
    )


@pytest.mark.django_db
def test_validate_activation(init_data):
    activation = init_data.activation
    user = init_data.user
    models.AwxToken.objects.create(
        user=user, name="test-token", token="test-token-value"
    )

    assert validate_activation(activation.id) is True


@pytest.mark.django_db
def test_validate_activation_without_token(init_data):
    activation = init_data.activation

    assert validate_activation(activation.id) is False
    activation.refresh_from_db()
    assert activation.status == ActivationStatus.ERROR
    assert activation.status_message == "No controller token specified"


@pytest.mark.django_db
def test_validate_activation_with_multiple_tokens(init_data):
    activation = init_data.activation
    user = init_data.user
    models.AwxToken.objects.create(
        user=user, name="test-token-1", token="test-token-value1"
    )
    models.AwxToken.objects.create(
        user=user, name="test-token-2", token="test-token-value2"
    )

    assert validate_activation(activation.id) is False
    activation.refresh_from_db()
    assert activation.status == ActivationStatus.ERROR
    assert (
        activation.status_message
        == "More than one controller token found, currently "
        "only 1 token is supported"
    )


@pytest.mark.django_db
def test_validate_activation_without_de(init_data):
    activation = init_data.activation
    user = init_data.user
    models.AwxToken.objects.create(
        user=user, name="test-token", token="test-token-value"
    )

    de = init_data.decision_environment
    de.delete()

    assert validate_activation(activation.id) is False
    activation.refresh_from_db()
    assert activation.status == ActivationStatus.ERROR
    assert activation.status_message == "No decision_environment specified"


@pytest.mark.django_db
def test_validate_activation_with_invalid_credential(init_data):
    activation = init_data.activation
    user = init_data.user
    models.AwxToken.objects.create(
        user=user, name="test-token", token="test-token-value"
    )

    with mock.patch.object(
        models.DecisionEnvironment, "credential"
    ) as credential_mock:
        credential_mock.id = 42

        assert validate_activation(activation.id) is False
        activation.refresh_from_db()
        assert activation.status == ActivationStatus.ERROR
        assert (
            activation.status_message
            == "credential matching query does not exist"
        )


@pytest.mark.parametrize(
    "dependent_attr",
    ["decision_environment", "rulebook", "extra_var"],
)
@pytest.mark.django_db
def test_validate_activation_with_invalid_dependent(init_data, dependent_attr):
    activation = init_data.activation
    user = init_data.user
    models.AwxToken.objects.create(
        user=user, name="test-token", token="test-token-value"
    )

    with mock.patch.object(models.Activation, dependent_attr) as de_mock:
        de_mock.id = 42

        assert validate_activation(activation.id) is False
        activation.refresh_from_db()
        assert activation.status == ActivationStatus.ERROR
        assert (
            activation.status_message
            == f"{dependent_attr} matching query does not exist"
        )
