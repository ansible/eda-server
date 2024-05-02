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
from unittest.mock import MagicMock, create_autospec

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
from aap_eda.services.activation.engine.common import ContainerEngine

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

DUMMY_GPG_KEY = """
-----BEGIN PGP PUBLIC KEY BLOCK-----

mQINBGYxK8IBEACzO/jIqIvEPsIE4xUCRC2WKiyzlD2rEmS/MYg9TMBYTVISrkGF
WfcQE0hPYU5qFeBzsr3qa/AfQobK+sv545QblAbNLINRdoaWnDMwVO+gLeVhrhbv
V2c7kwBe6ahQNy7cK/fh0OilNOwTC9V+HyHO/ZpUm5dniny+R4ScNiVtkegfg7mh
dDiFgAKOLgxElPUJiD/crnIqAWn2OAAqKb1LDGFOdHMJCwI1KH6XRjtmGxy5XX22
NC8zsE0TXfx4Oa8I7cxumZdh9Kw2wWxitSbpQnCT+8LapCwz36BjOjuEVw1c9AxN
UbFuVks1XhBG08SBnkFkAYD5ogTx2hs12PhWCIB2XneHBR7LmgaZzJiYtYoeehQ2
j6JPtIjdPEFgoVxYmSe74+VD/hIYg70Z0tpOpbB/xfvyvVZII/G2hha4l7YCCbN8
a14mN7HLTkaBx2NG7UtcZ5V1ahHznvtSVVqzkJQQqyJyD0sr8oivU3Aq0Cf8pqwL
PIg0Z2h7xCZ0pfxceMB4xFxJGosV+oq25QpasrbDWBhhQw91XpYnRvATYWn3ucU/
20Mn8ZeJOLQxGZLhOfV8rrzGan1czIURlsfnrCC81md3Q3mQTBVhrhTqXrrp7a1f
8ca6xL4d0yAntDudCPEpAOvYYbLsEwqRNNLu1/4uYgCDPsfXNGcTX8Ld9QARAQAB
tCN1c2VyQGFuc2libGUuY29tIDx1c2VyQGFuc2libGUuY29tPokCVAQTAQgAPhYh
BApWMhVpMJ19gBJOItYYZlMrZT/sBQJmMSvCAhsDBQkDwmcABQsJCAcCBhUKCQgL
AgQWAgMBAh4BAheAAAoJENYYZlMrZT/s56wP/1lvAntBZSCMZmTQ3AvpoIyGr2Hc
XwjUlDajYI9A/CdJuOTx/FEZCsfy64K3QCyE9fshozIjiLyuoFb9DPAQ6FKagV0b
Q1sCSSPk+ahaqSUGMQ7Lx8v+Xj0px9qYveeX1s5TisYBFZZPoiZcyhiJxdVZxP0D
kkN+frIfndtzCCEqnYG9XZMDe4LpAmQUExMhp/SvNnuLtEofnIau0ZFyrT+ZG2vm
KAIHyk2yE+N0fn+PzxYJJz77t8htOj/g+4XQZq/U4MhnMdge2raI7fCvh+OixFb0
7QGQpvxlAB0lO5vHf48PPYAgxgjXyiGWG0gpYAcx+t35BJRYlUWOzkjQYDzUvYfs
zGuOVnZbmlX4vtDaU27bMP0575IDtgRYa/p7J1M4BqNUicyelzbeCeSBd6NEyraU
c/deAZFD1MviBzFnbA5yXmxycbiEBmfpypfrsN8k/i4OU+bgZ2GgTLV3TcQcVulh
Z9yJGOc2CcGW9+bCPWOtxzb6ENAv4CmMyL9BmaXKYKXrKKOFnFgjVZU/SqsURoOD
FejSpTMyKeMS174YVm0qh7xw7nX1ph5mibHsS7sCfZCNywQfl91/hpalty7OeXqY
drC6WsDeShPiZlJT47AJgRfEMkZlA6DumlLikkbdCb4Mty2EhaGJ13WCGOzJ3z3k
RMVE39lIPjN2AKyK
=MlEN
-----END PGP PUBLIC KEY BLOCK-----
"""


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
def user_credential_type(
    default_organization: models.Organization,
) -> models.CredentialType:
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
        organization=default_organization,
    )


@pytest.fixture
def default_registry_credential(
    default_organization: models.Organization,
    preseed_credential_types,
) -> models.EdaCredential:
    """Return a default Container Registry Credential"""
    registry_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    return models.EdaCredential.objects.create(
        name="default-eda-credential",
        description="Default Registry Credential",
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
        name="managed-scm-credential",
        description="Default SCM Credential",
        credential_type=scm_credential_type,
        inputs=inputs_to_store(
            {"username": "dummy-user", "password": "dummy-password"}
        ),
        organization=default_organization,
    )


@pytest.fixture
def managed_registry_credential(
    default_organization: models.Organization,
    preseed_credential_types,
) -> models.EdaCredential:
    """Return a managed Eda Credential"""
    scm_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    return models.EdaCredential.objects.create(
        name="managed-eda-credential",
        description="Managed Registry Credential",
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


@pytest.fixture
def default_gpg_credential(
    default_organization: models.Organization,
    preseed_credential_types,
) -> models.EdaCredential:
    """Return a default GPG Credential"""
    gpg_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.GPG
    )
    return models.EdaCredential.objects.create(
        name="default-gpg-credential",
        description="Default GPG Credential",
        credential_type=gpg_credential_type,
        inputs=inputs_to_store({"gpg_public_key": DUMMY_GPG_KEY}),
        organization=default_organization,
    )


@pytest.fixture
def container_engine_mock() -> MagicMock:
    return create_autospec(ContainerEngine, instance=True)
