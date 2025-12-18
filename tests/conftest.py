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
from ansible_base.feature_flags.utils import (
    create_initial_data as seed_feature_flags,
)
from django.conf import settings

from aap_eda.core import enums, models
from aap_eda.core.management.commands.create_initial_data import (
    CREDENTIAL_TYPES,
    populate_credential_types,
)


#################################################################
# run tests setup
#################################################################
def pytest_runtest_setup(item):
    marker_expr = item.config.getoption("-m")

    if "multithreaded" in item.keywords and (
        not marker_expr or "multithreaded" not in marker_expr
    ):
        pytest.skip(
            "Skipped multithreaded test "
            "(not explicitly selected via `-m multithreaded`)"
        )


#################################################################
# Log capture factory
#################################################################
@pytest.fixture
def caplog_factory(caplog, request):
    def _factory(logger, level=logging.INFO):
        logger.setLevel(level)
        original_handlers = logger.handlers[:]
        logger.addHandler(caplog.handler)

        def restore_handlers():
            logger.removeHandler(caplog.handler)
            logger.handlers = original_handlers

        request.addfinalizer(restore_handlers)

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


@pytest.fixture
def preseed_feature_flags():
    seed_feature_flags()
