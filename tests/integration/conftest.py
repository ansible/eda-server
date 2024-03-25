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

import pytest
from django.conf import settings
from pytest_redis import factories

from aap_eda.core import models
from aap_eda.core.tasking import Queue

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

# fixture for pytest-redis plugin
# like django-db for a running redis server
redis_external = factories.redisdb("redis_nooproc")


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
    credential_type.refresh_from_db()

    return credential_type
