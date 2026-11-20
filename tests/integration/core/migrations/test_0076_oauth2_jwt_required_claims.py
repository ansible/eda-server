#  Copyright 2026 Red Hat, Inc.
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
from importlib import import_module

import pytest
from django.apps import apps

from aap_eda.core import enums, models
from aap_eda.core.management.commands.create_initial_data import (
    CREDENTIAL_TYPES,
    EVENT_STREAM_OAUTH2_JWT_INPUTS,
)

migration = import_module(
    "aap_eda.core.migrations.0076_oauth2_jwt_required_claims"
)


OAUTH2_JWT_DESCRIPTION = next(
    ctype["description"]
    for ctype in CREDENTIAL_TYPES
    if ctype["name"] == enums.EventStreamCredentialType.OAUTH2_JWT
)


def _field_ids(ctype):
    return [field["id"] for field in ctype.inputs["fields"]]


@pytest.fixture
def pre_migration_jwt_type(preseed_credential_types):
    """Emulate the OAuth2 JWT credential type as it existed before 0076."""
    ctype = models.CredentialType.objects.get(
        name=enums.EventStreamCredentialType.OAUTH2_JWT
    )
    ctype.inputs["fields"] = [
        field
        for field in ctype.inputs["fields"]
        if field["id"] != "required_claims"
    ]
    ctype.description = migration.OLD_DESCRIPTION
    ctype.save(update_fields=["inputs", "description"])
    return ctype


def test_migration_description_matches_create_initial_data():
    """The inlined migration description must stay in sync with seed data.

    The inlined field is covered by test_forward_adds_required_claims,
    which compares the migrated inputs to the seed data inputs.
    """
    assert migration.NEW_DESCRIPTION == OAUTH2_JWT_DESCRIPTION


@pytest.mark.django_db
def test_forward_adds_required_claims(pre_migration_jwt_type):
    migration.add_required_claims(apps, None)

    ctype = models.CredentialType.objects.get(pk=pre_migration_jwt_type.pk)
    assert ctype.inputs == EVENT_STREAM_OAUTH2_JWT_INPUTS
    assert _field_ids(ctype) == [
        "auth_type",
        "jwks_url",
        "audience",
        "required_claims",
        "http_header_key",
    ]
    assert ctype.description == OAUTH2_JWT_DESCRIPTION


@pytest.mark.django_db
def test_forward_is_idempotent(pre_migration_jwt_type):
    migration.add_required_claims(apps, None)
    migration.add_required_claims(apps, None)

    ctype = models.CredentialType.objects.get(pk=pre_migration_jwt_type.pk)
    assert _field_ids(ctype).count("required_claims") == 1


@pytest.mark.django_db
def test_forward_keeps_customized_description(pre_migration_jwt_type):
    pre_migration_jwt_type.description = "Custom description"
    pre_migration_jwt_type.save(update_fields=["description"])

    migration.add_required_claims(apps, None)

    ctype = models.CredentialType.objects.get(pk=pre_migration_jwt_type.pk)
    assert "required_claims" in _field_ids(ctype)
    assert ctype.description == "Custom description"


@pytest.mark.django_db
def test_backward_removes_required_claims(pre_migration_jwt_type):
    migration.add_required_claims(apps, None)
    migration.remove_required_claims(apps, None)

    ctype = models.CredentialType.objects.get(pk=pre_migration_jwt_type.pk)
    assert "required_claims" not in _field_ids(ctype)
    assert ctype.description == migration.OLD_DESCRIPTION
