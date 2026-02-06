#  Copyright 2025 Red Hat, Inc.
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

import copy
import tempfile

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import override_settings

from aap_eda.core import enums, models
from aap_eda.core.management.commands.create_initial_data import (
    POSTGRES_CREDENTIAL_INPUTS,
)
from aap_eda.core.utils.credentials import inputs_from_store
from aap_eda.core.utils.crypto.base import SecretValue


@pytest.mark.django_db
def test_create_initial_data_postgres_cred():
    call_command("create_initial_data")
    cred = models.EdaCredential.objects.get(
        name=settings.DEFAULT_SYSTEM_PG_NOTIFY_CREDENTIAL_NAME
    )
    assert cred


@pytest.mark.django_db
def test_create_initial_data_postgres_cred_with_cert():
    pgsslkey_file = tempfile.NamedTemporaryFile()
    with open(pgsslkey_file.name, "w") as f:
        f.write("Testing")

    pgsslcert_file = tempfile.NamedTemporaryFile()
    with open(pgsslcert_file.name, "w") as f:
        f.write("Testing")

    pgsslrootcert_file = tempfile.NamedTemporaryFile()
    with open(pgsslrootcert_file.name, "w") as f:
        f.write("Testing")

    value = copy.deepcopy(settings.DATABASES)
    value["default"]["OPTIONS"]["sslkey"] = pgsslkey_file.name
    value["default"]["OPTIONS"]["sslcert"] = pgsslcert_file.name
    value["default"]["OPTIONS"]["sslrootcert"] = pgsslrootcert_file.name

    with override_settings(DATABASES=value):
        call_command("create_initial_data")
        cred = models.EdaCredential.objects.get(
            name=settings.DEFAULT_SYSTEM_PG_NOTIFY_CREDENTIAL_NAME
        )
        assert cred


@pytest.mark.django_db
def test_create_initial_data_postgres_cred_with_missing_cert():
    missing_file = "/should_not_exist/_should_not_exist_pg_file_"
    value = copy.deepcopy(settings.DATABASES)
    value["default"]["OPTIONS"]["sslkey"] = missing_file
    value["default"]["OPTIONS"]["sslcert"] = missing_file
    value["default"]["OPTIONS"]["sslrootcert"] = missing_file

    with override_settings(DATABASES=value):
        with pytest.raises(ImproperlyConfigured):
            call_command("create_initial_data")


@pytest.mark.django_db
def test_create_initial_data_postgres_cred_with_event_stream_credentials():
    """Test that dedicated event stream credentials are used when
    both are set.
    """
    with override_settings(
        EVENT_STREAM_DB_USER="eda_event_stream",
        EVENT_STREAM_DB_PASSWORD="test_password",
    ):
        call_command("create_initial_data")
        cred = models.EdaCredential.objects.get(
            name=settings.DEFAULT_SYSTEM_PG_NOTIFY_CREDENTIAL_NAME
        )
        assert cred

        # Verify the credential uses the dedicated event stream user
        raw_inputs = (
            cred.inputs.get_secret_value()
            if isinstance(cred.inputs, SecretValue)
            else cred.inputs
        )
        decoded_inputs = inputs_from_store(raw_inputs)
        assert decoded_inputs["postgres_db_user"] == "eda_event_stream"
        assert decoded_inputs["postgres_db_password"] == "test_password"


@pytest.mark.django_db
def test_create_initial_data_fixes_outdated_postgres_credential_type():
    """Test that outdated credential type inputs are replaced with
    current schema.
    """
    # First run to create credential types
    call_command("create_initial_data")

    # Manually corrupt the credential type inputs
    cred_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.POSTGRES
    )
    outdated_inputs = {
        "fields": [{"id": "postgres_db_host", "label": "Invalid"}]
    }
    cred_type.inputs = outdated_inputs
    cred_type.save()

    # Ensure credential type inputs are corrupted
    cred_type.refresh_from_db()
    assert cred_type.inputs == outdated_inputs

    # Run again - should fix the inputs
    call_command("create_initial_data")

    # Verify inputs were replaced with current schema
    cred_type.refresh_from_db()
    assert cred_type.inputs == POSTGRES_CREDENTIAL_INPUTS
