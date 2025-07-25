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
"""Common Attributes for Activation Manager Tests."""

import pytest

from aap_eda.core import enums, models
from aap_eda.core.utils.credentials import inputs_to_store


@pytest.fixture
def default_de_credential(
    default_organization: models.Organization, preseed_credential_types
) -> models.EdaCredential:
    """Return a default Container Registry Credential"""
    registry_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    obj = models.EdaCredential.objects.create(
        name="default-de-credential",
        description="Default DE Credential",
        credential_type=registry_credential_type,
        inputs=inputs_to_store(
            {
                "username": "dummy-user",
                "password": "dummy-password",
                "host": "quay.io",
                "verify_ssl": False,
            }
        ),
        organization=default_organization,
    )
    obj.refresh_from_db()
    return obj


@pytest.fixture
def default_decision_environment(
    default_organization: models.Organization,
) -> models.DecisionEnvironment:
    """Return a default decision environment."""
    return models.DecisionEnvironment.objects.create(
        name="test-decision-environment",
        image_url="localhost:14000/test-image-url",
        organization=default_organization,
    )


@pytest.fixture
def default_decision_environment_with_credential(
    default_organization: models.Organization,
    default_de_credential: models.EdaCredential,
) -> models.DecisionEnvironment:
    """Return a default decision environment with credential."""
    return models.DecisionEnvironment.objects.create(
        name="test-decision-environment-with-credential",
        image_url="localhost:14000/test-image-url",
        organization=default_organization,
        eda_credential=default_de_credential,
    )


@pytest.fixture
def default_rulebook(
    default_organization: models.Organization,
) -> models.Rulebook:
    """Return a default rulebook."""
    rulesets = """
---
- name: Hello World
  hosts: all
  sources:
    - ansible.eda.range:
        limit: 5
  rules:
    - name: Say Hello
      condition: event.i == 1
      action:
        debug:
          msg: "Hello World!"

"""
    return models.Rulebook.objects.create(
        name="test-rulebook",
        rulesets=rulesets,
        organization=default_organization,
    )


@pytest.fixture
def default_user() -> models.User:
    """Return a default user."""
    user = models.User.objects.create(
        username="test.user",
        password="test.user.123",
        email="test.user@localhost",
    )

    return user
