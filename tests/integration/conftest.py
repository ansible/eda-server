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

import logging
from typing import Any, Dict

import pytest
import redis
from django.conf import settings

from aap_eda.core import enums, models
from aap_eda.core.management.commands.create_initial_data import (
    CREDENTIAL_TYPES,
    populate_credential_types,
)
from aap_eda.core.tasking import Queue
from aap_eda.core.utils.credentials import inputs_to_store

ADMIN_USERNAME = "test.admin"
ADMIN_PASSWORD = "test.admin.123"
INPUTS = {
    "fields": [
        {"id": "username", "label": "Username", "type": "string"},
        {
            "id": "password",
            "label": "Password",
            "type": "string",
            "secret": True,
        },
        {
            "id": "ssh_key_data",
            "label": "SCM Private Key",
            "type": "string",
            "format": "ssh_private_key",
            "secret": True,
            "multiline": True,
        },
        {
            "id": "ssh_key_unlock",
            "label": "Private Key Passphrase",
            "type": "string",
            "secret": True,
        },
    ]
}


# fixture for a running redis server
@pytest.fixture
def redis_external(redis_parameters):
    client = redis.Redis(**redis_parameters)
    yield client
    client.flushall()


@pytest.fixture
def test_queue_name():
    # Use a separately named copy of the default queue to prevent
    # cross-environment issues.  Using the eda-server default queue results in
    # tasks run by tests to execute within eda-server context, if the
    # eda-server default worker is running, rather than the test context.
    settings.RQ_QUEUES["test-default"] = settings.RQ_QUEUES["default"]
    return "test-default"


@pytest.fixture
def default_queue(test_queue_name, redis_external) -> Queue:
    return Queue(test_queue_name, connection=redis_external)


@pytest.fixture
def caplog_factory(caplog):
    def _factory(logger):
        logger.setLevel(logging.INFO)
        logger.handlers += [caplog.handler]
        return caplog

    return _factory


@pytest.fixture
def credential_type() -> models.CredentialType:
    """Return a default Credential Type."""
    credential_type = models.CredentialType.objects.create(
        name="default_credential_type", inputs=INPUTS, injectors={}
    )

    return credential_type


@pytest.fixture
def default_eda_credential(
    default_organization: models.Organization,
    preseed_credential_types,
) -> models.EdaCredential:
    """Return a default Credential"""
    registry_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    return models.EdaCredential.objects.create(
        name="default-eda-credential",
        description="Default EDA Credential",
        credential_type=registry_credential_type,
        inputs=inputs_to_store(
            {"username": "dummy-user", "password": "dummy-password"}
        ),
        organization=default_organization,
    )


@pytest.fixture
def default_vault_credential(
    default_organization: models.Organization,
    preseed_credential_types,
) -> models.EdaCredential:
    """Return a default Vault Credential"""
    vault_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.VAULT
    )
    return models.EdaCredential.objects.create(
        name="default-vault-credential",
        description="Default Vault Credential",
        credential_type=vault_credential_type,
        inputs=inputs_to_store(
            {"username": "dummy-user", "password": "dummy-password"}
        ),
        organization=default_organization,
    )


@pytest.fixture
def default_scm_credential(
    default_organization: models.Organization,
    preseed_credential_types,
) -> models.EdaCredential:
    """Return a managed Eda Credential"""
    scm_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.SOURCE_CONTROL
    )
    return models.EdaCredential.objects.create(
        name="managed-eda-credential",
        description="Default EDA Credential",
        credential_type=scm_credential_type,
        inputs=inputs_to_store(
            {"username": "dummy-user", "password": "dummy-password"}
        ),
        organization=default_organization,
    )


@pytest.fixture
def managed_eda_credential(
    default_organization: models.Organization,
    preseed_credential_types,
) -> models.EdaCredential:
    """Return a managed Eda Credential"""
    scm_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    return models.EdaCredential.objects.create(
        name="managed-eda-credential",
        description="Managed EDA Credential",
        credential_type=scm_credential_type,
        inputs=inputs_to_store(
            {"username": "dummy-user", "password": "dummy-password"}
        ),
        organization=default_organization,
        managed=True,
    )


@pytest.fixture
def credential_payload(
    default_organization: models.Organization,
    preseed_credential_types,
) -> Dict[str, Any]:
    """Return the payload for creating a new EdaCredential"""
    registry_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    return {
        "name": "test-credential",
        "description": "Test Credential",
        "credential_type": registry_credential_type,
        "inputs": {"username": "dummy-user", "password": "dummy-password"},
        "organization_id": default_organization.id,
    }


@pytest.fixture
def default_organization() -> models.Organization:
    "Corresponds to migration add_default_organization"
    return models.Organization.objects.get_or_create(
        name=settings.DEFAULT_ORGANIZATION_NAME,
        description="The default organization",
    )[0]


@pytest.fixture
def new_organization() -> models.Organization:
    "Return a new organization"
    return models.Organization.objects.create(
        name="new-organization",
        description="A new organization",
    )


@pytest.fixture
def default_team(default_organization: models.Organization) -> models.Team:
    """Return a default team in default_organization."""
    return models.Team.objects.create(
        name="Default Team",
        description="This is a default team.",
        organization=default_organization,
    )


@pytest.fixture
def new_team(default_organization: models.Organization) -> models.Team:
    """Return a new team in default_organization."""
    return models.Team.objects.create(
        name="New Team",
        description="This is a new team.",
        organization=default_organization,
    )


@pytest.fixture
def preseed_credential_types(
    default_organization: models.Organization,
) -> list[models.CredentialType]:
    """Preseed Credential Types."""
    return populate_credential_types(CREDENTIAL_TYPES)
