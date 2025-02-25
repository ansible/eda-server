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

import logging

import pytest
from django.conf import settings

from aap_eda.core import enums, models
from aap_eda.core.management.commands.create_initial_data import (
    CREDENTIAL_TYPES,
    populate_credential_types,
)
from aap_eda.settings import redis as redis_settings


#################################################################
# Log capture factory
#################################################################
@pytest.fixture
def caplog_factory(caplog):
    def _factory(logger):
        logger.setLevel(logging.INFO)
        logger.handlers += [caplog.handler]
        return caplog

    return _factory


#################################################################
# Organization
#################################################################
@pytest.fixture
def default_organization() -> models.Organization:
    "Corresponds to migration add_default_organization"
    return models.Organization.objects.get_or_create(
        name=settings.DEFAULT_ORGANIZATION_NAME,
        description="The default organization",
    )[0]


#################################################################
# DB
#################################################################
@pytest.fixture
def preseed_credential_types(
    default_organization: models.Organization,
) -> list[models.CredentialType]:
    """Preseed Credential Types."""
    return populate_credential_types(CREDENTIAL_TYPES)


@pytest.fixture
def aap_credential_type(preseed_credential_types):
    return models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.AAP
    )


#################################################################
# Redis
#################################################################
@pytest.fixture
def redis_parameters() -> dict:
    """Provide redis parameters based on settings values."""
    params = redis_settings.rq_redis_client_instantiation_parameters()

    # TODO: figure out the db oddity described here-in.
    #
    # There's an oddity with non-HA unit tests and the use of
    # an alternate db.
    #
    # For pragmatism we've removed the code here which attempted
    # to avoid conflicting with a deployed environment by using a
    # different database from that of the settings.
    #
    #
    # One constant is that DAB RedisCluster, which does not support
    # alternate dbs passes the EDA unit tests (which are part of
    # CI processing) and that by using only the 0 db
    # the same unit tests pass for non-HA whereas using an alternate
    # db as this code previously did results in non-HA unit tests
    # failing.
    #

    return params
