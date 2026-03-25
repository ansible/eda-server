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


@pytest.mark.django_db
def test_create_initial_data_postgres_cred_with_event_stream_sslmode():
    """Test that EVENT_STREAM_DB_SSLMODE overrides platform sslmode."""
    db_settings = copy.deepcopy(settings.DATABASES)
    db_settings["default"]["OPTIONS"]["sslmode"] = "prefer"

    with override_settings(
        DATABASES=db_settings,
        EVENT_STREAM_DB_USER="eda_event_stream",
        EVENT_STREAM_DB_PASSWORD="test_password",
        EVENT_STREAM_DB_SSLMODE="verify-full",
    ):
        call_command("create_initial_data")
        cred = models.EdaCredential.objects.get(
            name=settings.DEFAULT_SYSTEM_PG_NOTIFY_CREDENTIAL_NAME
        )

        raw_inputs = (
            cred.inputs.get_secret_value()
            if isinstance(cred.inputs, SecretValue)
            else cred.inputs
        )
        decoded_inputs = inputs_from_store(raw_inputs)

        # Should use explicit event stream sslmode, not platform's
        assert decoded_inputs["postgres_sslmode"] == "verify-full"


@pytest.mark.django_db
def test_create_initial_data_postgres_cred_with_event_stream_cert_auth():
    """Test that event stream cert auth uses dedicated certificate."""
    key_file = tempfile.NamedTemporaryFile()
    with open(key_file.name, "w") as f:
        f.write("Testing")

    cert_file = tempfile.NamedTemporaryFile()
    with open(cert_file.name, "w") as f:
        f.write("Testing")

    with override_settings(
        EVENT_STREAM_DB_USER="eda_event_stream",
        EVENT_STREAM_DB_SSLCERT=cert_file.name,
        EVENT_STREAM_DB_SSLKEY=key_file.name,
    ):
        call_command("create_initial_data")
        cred = models.EdaCredential.objects.get(
            name=settings.DEFAULT_SYSTEM_PG_NOTIFY_CREDENTIAL_NAME
        )
        assert cred

        raw_inputs = (
            cred.inputs.get_secret_value()
            if isinstance(cred.inputs, SecretValue)
            else cred.inputs
        )
        decoded_inputs = inputs_from_store(raw_inputs)

        # Should use event stream username
        assert decoded_inputs["postgres_db_user"] == "eda_event_stream"
        # Should have empty password for cert auth
        assert decoded_inputs["postgres_db_password"] == ""
        # Should include certificate content
        assert "Testing" in decoded_inputs["postgres_sslcert"]
        assert "Testing" in decoded_inputs["postgres_sslkey"]


@pytest.mark.django_db
def test_create_initial_data_postgres_cred_no_leak_platform_certs():
    """Test platform cert/key are not included when using password auth."""
    # Create temporary files for main DB cert/key
    key_file = tempfile.NamedTemporaryFile()
    with open(key_file.name, "w") as f:
        f.write("Testing")

    cert_file = tempfile.NamedTemporaryFile()
    with open(cert_file.name, "w") as f:
        f.write("Testing")

    rootcert_file = tempfile.NamedTemporaryFile()
    with open(rootcert_file.name, "w") as f:
        f.write("Testing")

    # Simulate main DB using cert auth, but event streams using password auth
    db_settings = copy.deepcopy(settings.DATABASES)
    db_settings["default"]["OPTIONS"] = {
        "sslmode": "verify-full",
        "sslcert": cert_file.name,
        "sslkey": key_file.name,
        "sslrootcert": rootcert_file.name,
    }

    with override_settings(
        # No EVENT_STREAM_DB_SSLCERT/SSLKEY - using password auth
        DATABASES=db_settings,
        EVENT_STREAM_DB_USER="eda_event_stream",
        EVENT_STREAM_DB_PASSWORD="test_password",
    ):
        call_command("create_initial_data")
        cred = models.EdaCredential.objects.get(
            name=settings.DEFAULT_SYSTEM_PG_NOTIFY_CREDENTIAL_NAME
        )
        assert cred

        raw_inputs = (
            cred.inputs.get_secret_value()
            if isinstance(cred.inputs, SecretValue)
            else cred.inputs
        )
        decoded_inputs = inputs_from_store(raw_inputs)

        # Should NOT contain platform cert/key
        assert decoded_inputs["postgres_sslcert"] == ""
        assert decoded_inputs["postgres_sslkey"] == ""
        # Should still have CA cert for server verification
        assert "Testing" in decoded_inputs["postgres_sslrootcert"]
        # Should use password auth credentials
        assert decoded_inputs["postgres_db_user"] == "eda_event_stream"
        assert decoded_inputs["postgres_db_password"] == "test_password"


@pytest.mark.django_db
def test_create_initial_data_rule_engine_cred_not_created_without_host():
    """Test that no rule engine credential is created when
    EVENT_PERSISTENCE_DB_HOST is not set.
    """
    call_command("create_initial_data")
    assert not models.EdaCredential.objects.filter(
        name=settings.DEFAULT_SYSTEM_RULE_ENGINE_CREDENTIAL_NAME
    ).exists()


@pytest.mark.django_db
def test_create_initial_data_rule_engine_cred_with_password_auth():
    """Test that the rule engine credential is created with password auth."""
    with override_settings(
        EVENT_PERSISTENCE_DB_HOST="ep-host",
        EVENT_PERSISTENCE_DB_PORT=5433,
        EVENT_PERSISTENCE_DB_NAME="custom_db",
        EVENT_PERSISTENCE_DB_USER="ep_user",
        EVENT_PERSISTENCE_DB_PASSWORD="ep_password",
        EVENT_PERSISTENCE_PGSSLMODE="verify-full",
    ):
        call_command("create_initial_data")
        cred = models.EdaCredential.objects.get(
            name=settings.DEFAULT_SYSTEM_RULE_ENGINE_CREDENTIAL_NAME
        )
        assert cred.managed is True
        assert (
            cred.credential_type.name
            == enums.DefaultCredentialType.EDA_RULE_ENGINE
        )

        raw_inputs = (
            cred.inputs.get_secret_value()
            if isinstance(cred.inputs, SecretValue)
            else cred.inputs
        )
        decoded_inputs = inputs_from_store(raw_inputs)

        assert decoded_inputs["postgres_db_host"] == "ep-host"
        assert decoded_inputs["postgres_db_port"] == "5433"
        assert decoded_inputs["postgres_db_name"] == "custom_db"
        assert decoded_inputs["postgres_db_user"] == "ep_user"
        assert decoded_inputs["postgres_db_password"] == "ep_password"
        assert decoded_inputs["postgres_sslmode"] == "verify-full"


@pytest.mark.django_db
def test_create_initial_data_rule_engine_cred_missing_required():
    """Test that ImproperlyConfigured is raised when host is set
    but other required settings are missing.
    """
    with override_settings(
        EVENT_PERSISTENCE_DB_HOST="ep-host",
        EVENT_PERSISTENCE_DB_PORT=None,
        EVENT_PERSISTENCE_DB_USER=None,
        EVENT_PERSISTENCE_DB_PASSWORD=None,
    ):
        with pytest.raises(ImproperlyConfigured, match="required settings"):
            call_command("create_initial_data")


@pytest.mark.django_db
def test_create_initial_data_rule_engine_cred_cert_auth():
    """Test that cert auth does not require a password."""
    cert_file = tempfile.NamedTemporaryFile()
    with open(cert_file.name, "w") as f:
        f.write("rule-engine-cert")

    key_file = tempfile.NamedTemporaryFile()
    with open(key_file.name, "w") as f:
        f.write("rule-engine-key")

    with override_settings(
        EVENT_PERSISTENCE_DB_HOST="ep-host",
        EVENT_PERSISTENCE_DB_PORT=5432,
        EVENT_PERSISTENCE_DB_USER="ep_user",
        EVENT_PERSISTENCE_DB_PASSWORD=None,
        EVENT_PERSISTENCE_PGSSLCERT=cert_file.name,
        EVENT_PERSISTENCE_PGSSLKEY=key_file.name,
    ):
        call_command("create_initial_data")
        cred = models.EdaCredential.objects.get(
            name=settings.DEFAULT_SYSTEM_RULE_ENGINE_CREDENTIAL_NAME
        )

        raw_inputs = (
            cred.inputs.get_secret_value()
            if isinstance(cred.inputs, SecretValue)
            else cred.inputs
        )
        decoded_inputs = inputs_from_store(raw_inputs)

        assert decoded_inputs["postgres_db_password"] == ""
        assert "rule-engine-cert" in decoded_inputs["postgres_sslcert"]
        assert "rule-engine-key" in decoded_inputs["postgres_sslkey"]


@pytest.mark.django_db
def test_create_initial_data_rule_engine_cred_with_rootcert():
    """Test that rootcert is read when provided."""
    rootcert_file = tempfile.NamedTemporaryFile()
    with open(rootcert_file.name, "w") as f:
        f.write("rule-engine-rootcert")

    with override_settings(
        EVENT_PERSISTENCE_DB_HOST="ep-host",
        EVENT_PERSISTENCE_DB_PORT=5432,
        EVENT_PERSISTENCE_DB_USER="ep_user",
        EVENT_PERSISTENCE_DB_PASSWORD="ep_password",
        EVENT_PERSISTENCE_PGSSLROOTCERT=rootcert_file.name,
    ):
        call_command("create_initial_data")
        cred = models.EdaCredential.objects.get(
            name=settings.DEFAULT_SYSTEM_RULE_ENGINE_CREDENTIAL_NAME
        )

        raw_inputs = (
            cred.inputs.get_secret_value()
            if isinstance(cred.inputs, SecretValue)
            else cred.inputs
        )
        decoded_inputs = inputs_from_store(raw_inputs)

        assert "rule-engine-rootcert" in decoded_inputs["postgres_sslrootcert"]
