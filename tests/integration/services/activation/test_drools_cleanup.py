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
"""Tests for drools_cleanup module."""

import os
from unittest.mock import MagicMock, patch

import psycopg
import pytest

from aap_eda.core import enums, models
from aap_eda.core.utils.credentials import inputs_to_store
from aap_eda.services.activation.drools_cleanup import (
    _delete_rows_by_ha_uuid,
    _temp_cert_files,
    drools_cleanup,
)


class TestTempCertFiles:
    """Tests for _temp_cert_files context manager."""

    def test_no_certificates(self):
        """Test no files created when no certificate content provided."""
        with _temp_cert_files() as (sslcert, sslkey, sslrootcert):
            assert sslcert is None
            assert sslkey is None
            assert sslrootcert is None

    def test_all_certificates(self):
        """Test all certificate files created with proper permissions."""
        cert_content = (
            "-----BEGIN CERTIFICATE-----\ntest cert\n-----END CERTIFICATE-----"
        )
        key_content = (
            "-----BEGIN PRIVATE KEY-----\ntest key\n-----END PRIVATE KEY-----"
        )
        ca_content = (
            "-----BEGIN CERTIFICATE-----\ntest ca\n-----END CERTIFICATE-----"
        )

        with _temp_cert_files(
            sslcert_content=cert_content,
            sslkey_content=key_content,
            sslrootcert_content=ca_content,
        ) as (sslcert_path, sslkey_path, sslrootcert_path):
            # Verify all paths are created
            assert sslcert_path is not None
            assert sslkey_path is not None
            assert sslrootcert_path is not None

            # Verify files exist
            assert os.path.exists(sslcert_path)
            assert os.path.exists(sslkey_path)
            assert os.path.exists(sslrootcert_path)

            # Verify content
            with open(sslcert_path, "r") as f:
                assert f.read() == cert_content
            with open(sslkey_path, "r") as f:
                assert f.read() == key_content
            with open(sslrootcert_path, "r") as f:
                assert f.read() == ca_content

            # Verify permissions
            # Client cert should be restrictive (0o600)
            cert_stat = os.stat(sslcert_path)
            assert oct(cert_stat.st_mode)[-3:] == "600"

            # Private key should be restrictive (0o600)
            key_stat = os.stat(sslkey_path)
            assert oct(key_stat.st_mode)[-3:] == "600"

            # CA cert should be restrictive (0o600)
            ca_stat = os.stat(sslrootcert_path)
            assert oct(ca_stat.st_mode)[-3:] == "600"

            # Store temp dir for cleanup verification
            temp_dir = os.path.dirname(sslcert_path)

        # Verify cleanup: files should be deleted
        assert not os.path.exists(sslcert_path)
        assert not os.path.exists(sslkey_path)
        assert not os.path.exists(sslrootcert_path)
        assert not os.path.exists(temp_dir)

    def test_only_ca_certificate(self):
        """Test only CA certificate created when only CA content provided."""
        ca_content = (
            "-----BEGIN CERTIFICATE-----\ntest ca\n-----END CERTIFICATE-----"
        )

        with _temp_cert_files(sslrootcert_content=ca_content) as (
            sslcert_path,
            sslkey_path,
            sslrootcert_path,
        ):
            assert sslcert_path is None
            assert sslkey_path is None
            assert sslrootcert_path is not None
            assert os.path.exists(sslrootcert_path)

            with open(sslrootcert_path, "r") as f:
                assert f.read() == ca_content

    def test_cleanup_on_exception(self):
        """Test that files are cleaned up even when an exception occurs."""
        cert_content = (
            "-----BEGIN CERTIFICATE-----\ntest cert\n-----END CERTIFICATE-----"
        )

        temp_paths = {}
        with pytest.raises(ValueError):
            with _temp_cert_files(sslcert_content=cert_content) as (
                sslcert_path,
                sslkey_path,
                sslrootcert_path,
            ):
                temp_paths["cert"] = sslcert_path
                temp_paths["dir"] = os.path.dirname(sslcert_path)
                raise ValueError("Test exception")

        # Verify cleanup even after exception
        assert not os.path.exists(temp_paths["cert"])
        assert not os.path.exists(temp_paths["dir"])


class TestDeleteRowsByHaUuid:
    """Tests for _delete_rows_by_ha_uuid function."""

    @patch("aap_eda.services.activation.drools_cleanup.psycopg.connect")
    def test_successful_deletion_with_password(self, mock_connect):
        """Test successful deletion with password authentication."""
        # Setup mocks
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock table existence checks (all tables exist)
        mock_cursor.fetchone.return_value = [True]
        # Mock row counts for deletions
        mock_cursor.rowcount = 10

        result = _delete_rows_by_ha_uuid(
            ha_uuid="test-uuid-123",
            postgres_db_host="localhost",
            postgres_db_port="5432",
            postgres_db_name="eda",
            postgres_db_user="postgres",
            postgres_db_password="secret",
            postgres_sslmode="require",
        )

        # Verify connection parameters
        mock_connect.assert_called_once()
        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["host"] == "localhost"
        assert call_kwargs["port"] == 5432
        assert call_kwargs["dbname"] == "eda"
        assert call_kwargs["user"] == "postgres"
        assert call_kwargs["password"] == "secret"
        assert call_kwargs["sslmode"] == "require"
        assert call_kwargs["autocommit"] is True

        # Verify results
        assert result == {
            "drools_ansible_action_info": 10,
            "drools_ansible_ha_stats": 10,
            "drools_ansible_matching_event": 10,
            "drools_ansible_session_state": 10,
        }

        # Verify DELETE queries were executed
        delete_calls = [
            call
            for call in mock_cursor.execute.call_args_list
            if "DELETE FROM" in str(call)
        ]
        assert len(delete_calls) == 4

    @patch("aap_eda.services.activation.drools_cleanup.psycopg.connect")
    @patch("aap_eda.services.activation.drools_cleanup._temp_cert_files")
    def test_deletion_with_mtls(self, mock_temp_cert_files, mock_connect):
        """Test deletion with mTLS (client certificate) authentication."""
        # Setup mocks
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock certificate paths
        mock_temp_cert_files.return_value.__enter__.return_value = (
            "/tmp/client.crt",
            "/tmp/client.key",
            "/tmp/ca.crt",
        )

        # Mock table existence checks
        mock_cursor.fetchone.return_value = [True]
        mock_cursor.rowcount = 5

        cert_content = (
            "-----BEGIN CERTIFICATE-----\ncert\n-----END CERTIFICATE-----"
        )
        key_content = (
            "-----BEGIN PRIVATE KEY-----\nkey\n-----END PRIVATE KEY-----"
        )
        ca_content = (
            "-----BEGIN CERTIFICATE-----\nca\n-----END CERTIFICATE-----"
        )

        result = _delete_rows_by_ha_uuid(
            ha_uuid="test-uuid-123",
            postgres_db_host="dbhost.example.com",
            postgres_db_port="5432",
            postgres_db_name="eda",
            postgres_db_user="postgres",
            postgres_sslmode="verify-full",
            postgres_sslcert=cert_content,
            postgres_sslkey=key_content,
            postgres_sslrootcert=ca_content,
            postgres_sslpassword="keypass",
        )

        # Verify _temp_cert_files was called with correct content
        mock_temp_cert_files.assert_called_once_with(
            sslcert_content=cert_content,
            sslkey_content=key_content,
            sslrootcert_content=ca_content,
        )

        # Verify connection parameters include cert paths
        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["sslcert"] == "/tmp/client.crt"
        assert call_kwargs["sslkey"] == "/tmp/client.key"
        assert call_kwargs["sslrootcert"] == "/tmp/ca.crt"
        assert call_kwargs["sslpassword"] == "keypass"
        assert call_kwargs["sslmode"] == "verify-full"

        # Verify results
        assert len(result) == 4
        assert all(count == 5 for count in result.values())

    @patch("aap_eda.services.activation.drools_cleanup.psycopg.connect")
    def test_nonexistent_tables(self, mock_connect):
        """Test behavior when some tables don't exist."""
        # Setup mocks
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock table existence checks: first two exist, last two don't
        mock_cursor.fetchone.side_effect = [[True], [True], [False], [False]]
        mock_cursor.rowcount = 3

        with patch(
            "aap_eda.services.activation.drools_cleanup.LOGGER"
        ) as mock_logger:
            result = _delete_rows_by_ha_uuid(
                ha_uuid="test-uuid-123",
                postgres_db_password="secret",
            )

        # Verify only existing tables were deleted from
        assert result == {
            "drools_ansible_action_info": 3,
            "drools_ansible_ha_stats": 3,
            "drools_ansible_matching_event": 0,
            "drools_ansible_session_state": 0,
        }

        # Verify warnings were logged for nonexistent tables
        warning_calls = [
            call
            for call in mock_logger.warning.call_args_list
            if "does not exist" in str(call)
        ]
        assert len(warning_calls) == 2

    @patch("aap_eda.services.activation.drools_cleanup.psycopg.connect")
    def test_connection_error(self, mock_connect):
        """Test handling of database connection errors."""
        mock_connect.side_effect = psycopg.OperationalError(
            "Connection failed"
        )

        with patch(
            "aap_eda.services.activation.drools_cleanup.LOGGER"
        ) as mock_logger:
            result = _delete_rows_by_ha_uuid(
                ha_uuid="test-uuid-123",
                postgres_db_password="secret",
            )

        # Verify empty result is returned on error
        assert result == {}

        # Verify error was logged
        mock_logger.error.assert_called_once()
        assert "Error during Drools cleanup" in str(
            mock_logger.error.call_args
        )

    @patch("aap_eda.services.activation.drools_cleanup.psycopg.connect")
    def test_autocommit_false(self, mock_connect):
        """Test manual commit when autocommit is False."""
        # Setup mocks
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchone.return_value = [True]
        mock_cursor.rowcount = 1

        _delete_rows_by_ha_uuid(
            ha_uuid="test-uuid-123",
            postgres_db_password="secret",
            autocommit=False,
        )

        # Verify autocommit was False
        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["autocommit"] is False

        # Verify manual commit was called
        mock_conn.commit.assert_called_once()

    @patch("aap_eda.services.activation.drools_cleanup.psycopg.connect")
    def test_sql_injection_prevention(self, mock_connect):
        """Test SQL injection prevented through parameterized queries."""
        # Setup mocks
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchone.return_value = [True]
        mock_cursor.rowcount = 0

        # Try with malicious ha_uuid
        malicious_uuid = "'; DROP TABLE users; --"

        _delete_rows_by_ha_uuid(
            ha_uuid=malicious_uuid,
            postgres_db_password="secret",
        )

        # Verify parameterized queries were used (ha_uuid passed as parameter)
        delete_calls = [
            call
            for call in mock_cursor.execute.call_args_list
            if "DELETE FROM" in str(call)
        ]

        for call in delete_calls:
            # Second argument should be the tuple of parameters
            assert len(call[0]) == 2  # query and parameters
            assert call[0][1] == (malicious_uuid,)


@pytest.mark.django_db
class TestDroolsCleanup:
    """Tests for drools_cleanup function."""

    @pytest.fixture
    def rule_engine_credential_type(
        self, preseed_credential_types
    ) -> models.CredentialType:
        """Return rule engine credential type."""
        return models.CredentialType.objects.get(
            name=enums.DefaultCredentialType.EDA_RULE_ENGINE
        )

    @pytest.fixture
    def rule_engine_credential(
        self,
        default_organization: models.Organization,
        rule_engine_credential_type,
    ) -> models.EdaCredential:
        """Return a rule engine credential with password auth."""
        obj = models.EdaCredential.objects.create(
            name="test-rule-engine-credential",
            description="Test Rule Engine Credential",
            credential_type=rule_engine_credential_type,
            inputs=inputs_to_store(
                {
                    "postgres_db_host": "localhost",
                    "postgres_db_port": "5432",
                    "postgres_db_name": "eda",
                    "postgres_db_user": "postgres",
                    "postgres_db_password": "secret123",
                    "postgres_sslmode": "require",
                }
            ),
            organization=default_organization,
        )
        obj.refresh_from_db()
        return obj

    @pytest.fixture
    def rule_engine_credential_mtls(
        self,
        default_organization: models.Organization,
        rule_engine_credential_type,
    ) -> models.EdaCredential:
        """Return a rule engine credential with mTLS auth."""
        obj = models.EdaCredential.objects.create(
            name="test-rule-engine-credential-mtls",
            description="Test Rule Engine Credential with mTLS",
            credential_type=rule_engine_credential_type,
            inputs=inputs_to_store(
                {
                    "postgres_db_host": "dbhost.example.com",
                    "postgres_db_port": "5432",
                    "postgres_db_name": "eda",
                    "postgres_db_user": "postgres",
                    "postgres_sslmode": "verify-full",
                    "postgres_sslcert": (
                        "-----BEGIN CERTIFICATE-----\ncert\n"
                        "-----END CERTIFICATE-----"
                    ),
                    "postgres_sslkey": (
                        "-----BEGIN PRIVATE KEY-----\nkey\n"
                        "-----END PRIVATE KEY-----"
                    ),
                    "postgres_sslrootcert": (
                        "-----BEGIN CERTIFICATE-----\nca\n"
                        "-----END CERTIFICATE-----"
                    ),
                }
            ),
            organization=default_organization,
        )
        obj.refresh_from_db()
        return obj

    @pytest.fixture
    def activation_with_rule_engine_cred(
        self,
        default_activation: models.Activation,
        rule_engine_credential: models.EdaCredential,
    ) -> models.Activation:
        """Return an activation with rule engine credential."""
        default_activation.rule_engine_credential = rule_engine_credential
        default_activation.save(update_fields=["rule_engine_credential"])
        return default_activation

    @patch(
        "aap_eda.services.activation.drools_cleanup._delete_rows_by_ha_uuid"
    )
    def test_drools_cleanup_with_credential(
        self, mock_delete, activation_with_rule_engine_cred
    ):
        """Test drools_cleanup with rule engine credential."""
        mock_delete.return_value = {
            "drools_ansible_action_info": 5,
            "drools_ansible_ha_stats": 3,
            "drools_ansible_matching_event": 10,
            "drools_ansible_session_state": 2,
        }

        activation = activation_with_rule_engine_cred

        with patch(
            "aap_eda.services.activation.drools_cleanup.LOGGER"
        ) as mock_logger:
            drools_cleanup(activation)

        # Verify _delete_rows_by_ha_uuid was called
        mock_delete.assert_called_once()

        # Verify first argument is the activation ID as string
        call_args = mock_delete.call_args[0]
        assert call_args[0] == str(activation.id)

        # Verify connection parameters were passed
        call_kwargs = mock_delete.call_args[1]
        assert call_kwargs["postgres_db_host"] == "localhost"
        assert call_kwargs["postgres_db_port"] == "5432"
        assert call_kwargs["postgres_db_name"] == "eda"
        assert call_kwargs["postgres_db_user"] == "postgres"
        assert call_kwargs["postgres_db_password"] == "secret123"
        assert call_kwargs["postgres_sslmode"] == "require"

        # Verify logging
        info_calls = [
            call
            for call in mock_logger.info.call_args_list
            if "Deleting Drools" in str(call) or "Deleted Drools" in str(call)
        ]
        assert len(info_calls) == 2

    @patch(
        "aap_eda.services.activation.drools_cleanup._delete_rows_by_ha_uuid"
    )
    def test_drools_cleanup_with_mtls_credential(
        self,
        mock_delete,
        default_activation: models.Activation,
        rule_engine_credential_mtls: models.EdaCredential,
    ):
        """Test drools_cleanup with mTLS credential."""
        default_activation.rule_engine_credential = rule_engine_credential_mtls
        default_activation.save(update_fields=["rule_engine_credential"])

        mock_delete.return_value = {"drools_ansible_action_info": 1}

        drools_cleanup(default_activation)

        # Verify certificate parameters were passed
        call_kwargs = mock_delete.call_args[1]
        assert "postgres_sslcert" in call_kwargs
        assert "postgres_sslkey" in call_kwargs
        assert "postgres_sslrootcert" in call_kwargs
        assert "BEGIN CERTIFICATE" in call_kwargs["postgres_sslcert"]
        assert "BEGIN PRIVATE KEY" in call_kwargs["postgres_sslkey"]
        assert "BEGIN CERTIFICATE" in call_kwargs["postgres_sslrootcert"]

    @patch(
        "aap_eda.services.activation.drools_cleanup._delete_rows_by_ha_uuid"
    )
    @patch(
        "aap_eda.services.activation.drools_cleanup."
        "get_default_rule_engine_credential"
    )
    def test_drools_cleanup_with_default_credential(
        self,
        mock_get_default,
        mock_delete,
        default_activation: models.Activation,
        rule_engine_credential: models.EdaCredential,
    ):
        """Test drools_cleanup with default credential fallback."""
        # Activation has no rule_engine_credential
        assert default_activation.rule_engine_credential is None

        # Mock the default credential
        mock_get_default.return_value = rule_engine_credential
        mock_delete.return_value = {}

        drools_cleanup(default_activation)

        # Verify default credential was fetched
        mock_get_default.assert_called_once()

        # Verify deletion was attempted
        mock_delete.assert_called_once()

    @patch(
        "aap_eda.services.activation.drools_cleanup._delete_rows_by_ha_uuid"
    )
    @patch(
        "aap_eda.services.activation.drools_cleanup."
        "get_default_rule_engine_credential"
    )
    def test_drools_cleanup_no_credential(
        self,
        mock_get_default,
        mock_delete,
        default_activation: models.Activation,
    ):
        """Test drools_cleanup when no credential is available."""
        # No credential on activation and no default
        assert default_activation.rule_engine_credential is None
        mock_get_default.return_value = None

        drools_cleanup(default_activation)

        # Verify default credential was checked
        mock_get_default.assert_called_once()

        # Verify deletion was NOT attempted
        mock_delete.assert_not_called()

    @patch(
        "aap_eda.services.activation.drools_cleanup._delete_rows_by_ha_uuid"
    )
    def test_drools_cleanup_filters_invalid_params(
        self, mock_delete, activation_with_rule_engine_cred
    ):
        """Test that drools_cleanup filters out invalid parameters."""
        mock_delete.return_value = {}

        # Mock get_resolved_secrets to return extra parameters
        with patch(
            "aap_eda.services.activation.drools_cleanup.get_resolved_secrets"
        ) as mock_get_secrets:
            mock_get_secrets.return_value = {
                "postgres_db_host": "localhost",
                "postgres_db_port": "5432",
                "invalid_param_1": "should_be_filtered",
                "postgres_db_name": "eda",
                "another_invalid": "also_filtered",
                "postgres_db_user": "postgres",
                "postgres_db_password": "secret",
            }

            drools_cleanup(activation_with_rule_engine_cred)

        # Verify only valid parameters were passed
        call_kwargs = mock_delete.call_args[1]
        assert "postgres_db_host" in call_kwargs
        assert "postgres_db_port" in call_kwargs
        assert "postgres_db_name" in call_kwargs
        assert "postgres_db_user" in call_kwargs
        assert "postgres_db_password" in call_kwargs
        assert "invalid_param_1" not in call_kwargs
        assert "another_invalid" not in call_kwargs
