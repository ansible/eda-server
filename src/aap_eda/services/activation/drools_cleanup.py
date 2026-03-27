"""Delete rows from drools tables based on ha_uuid."""
import logging
import os
import tempfile
from contextlib import contextmanager
from typing import Optional

import psycopg

from aap_eda.core.models import Activation
from aap_eda.core.models.utils import get_default_rule_engine_credential
from aap_eda.core.utils.credentials import get_resolved_secrets

LOGGER = logging.getLogger(__name__)


def _write_cert_file(
    temp_dir: str, filename: str, content: str, mode: int
) -> str:
    """Write certificate content to a file with specified permissions.

    Args:
        temp_dir: Directory to write the file to
        filename: Name of the file to create
        content: Content to write to the file
        mode: File permissions mode (e.g., 0o600, 0o644)

    Returns:
        Path to the created file
    """
    file_path = os.path.join(temp_dir, filename)
    with open(file_path, "w") as f:
        f.write(content)
    os.chmod(file_path, mode)
    return file_path


def _cleanup_temp_dir(temp_dir: str) -> None:
    """Remove all files in temp directory and the directory itself.

    Args:
        temp_dir: Directory to clean up
    """
    if not temp_dir or not os.path.exists(temp_dir):
        return

    for filename in os.listdir(temp_dir):
        file_path = os.path.join(temp_dir, filename)
        try:
            os.remove(file_path)
        except Exception:
            pass
    try:
        os.rmdir(temp_dir)
    except Exception:
        pass


@contextmanager
def _temp_cert_files(
    sslcert_content: Optional[str] = None,
    sslkey_content: Optional[str] = None,
    sslrootcert_content: Optional[str] = None,
):
    """Context manager to create temporary certificate files.

    Yields paths to the temporary files and cleans them up on exit.

    Args:
        sslcert_content: Client certificate content as string
        sslkey_content: Client private key content as string
        sslrootcert_content: CA certificate content as string

    Yields:
        Tuple of (sslcert_path, sslkey_path, sslrootcert_path) or
        (None, None, None)
    """
    temp_dir = None
    sslcert_path = None
    sslkey_path = None
    sslrootcert_path = None

    try:
        # Only create temp directory if we have cert content to write
        if sslcert_content or sslkey_content or sslrootcert_content:
            temp_dir = tempfile.mkdtemp(prefix="pg_certs_")

            # CA cert - owner read/write only (0o600)
            if sslrootcert_content:
                sslrootcert_path = _write_cert_file(
                    temp_dir, "ca.crt", sslrootcert_content, 0o600
                )

            # Client cert - owner read/write only (0o600)
            if sslcert_content:
                sslcert_path = _write_cert_file(
                    temp_dir, "client.crt", sslcert_content, 0o600
                )

            # Private key - owner read/write only
            # (0o600 - required by PostgreSQL)
            if sslkey_content:
                sslkey_path = _write_cert_file(
                    temp_dir, "client.key", sslkey_content, 0o600
                )

        yield sslcert_path, sslkey_path, sslrootcert_path

    finally:
        _cleanup_temp_dir(temp_dir)


def _build_connection_params(
    postgres_db_host: str,
    postgres_db_port: str,
    postgres_db_name: str,
    postgres_db_user: str,
    postgres_sslmode: str,
    postgres_db_password: Optional[str],
    postgres_sslpassword: Optional[str],
    sslcert_path: Optional[str],
    sslkey_path: Optional[str],
    sslrootcert_path: Optional[str],
) -> dict:
    """Build PostgreSQL connection parameters.

    Args:
        postgres_db_host: Database host
        postgres_db_port: Database port
        postgres_db_name: Database name
        postgres_db_user: Database user
        postgres_sslmode: SSL mode
        postgres_db_password: Database password (optional)
        postgres_sslpassword: SSL key password (optional)
        sslcert_path: Path to client certificate file (optional)
        sslkey_path: Path to client private key file (optional)
        sslrootcert_path: Path to CA certificate file (optional)

    Returns:
        Dictionary of connection parameters for psycopg
    """
    conn_params = {
        "host": postgres_db_host,
        "port": int(postgres_db_port),
        "dbname": postgres_db_name,
        "user": postgres_db_user,
        "sslmode": postgres_sslmode,
    }

    # Add optional parameters if provided
    if postgres_db_password:
        conn_params["password"] = postgres_db_password
    if sslcert_path:
        conn_params["sslcert"] = sslcert_path
    if sslkey_path:
        conn_params["sslkey"] = sslkey_path
    if sslrootcert_path:
        conn_params["sslrootcert"] = sslrootcert_path
    if postgres_sslpassword:
        conn_params["sslpassword"] = postgres_sslpassword

    return conn_params


def _table_exists(cursor, table_name: str) -> bool:
    """Check if a table exists in the public schema.

    Args:
        cursor: Database cursor
        table_name: Name of the table to check

    Returns:
        True if table exists, False otherwise
    """
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = %s
        )
        """,
        (table_name,),
    )
    return cursor.fetchone()[0]


def _delete_from_table(cursor, table_name: str, ha_uuid: str) -> int:
    """Delete rows from a table by ha_uuid.

    Args:
        cursor: Database cursor
        table_name: Name of the table to delete from
        ha_uuid: The ha_uuid value to match for deletion

    Returns:
        Number of rows deleted
    """
    query = f"DELETE FROM {table_name} WHERE ha_uuid = %s"
    cursor.execute(query, (ha_uuid,))
    return cursor.rowcount


def _delete_rows_by_ha_uuid(
    ha_uuid: str,
    postgres_db_host: str = "localhost",
    postgres_db_port: str = "5432",
    postgres_db_name: str = "eda",
    postgres_db_user: str = "postgres",
    postgres_db_password: Optional[str] = None,
    postgres_sslmode: str = "prefer",
    postgres_sslcert: Optional[str] = None,
    postgres_sslkey: Optional[str] = None,
    postgres_sslpassword: Optional[str] = None,
    postgres_sslrootcert: Optional[str] = None,
    autocommit: bool = True,
) -> dict[str, int]:
    """
    Delete rows from drools tables where ha_uuid matches.

    Args:
        ha_uuid: The ha_uuid value to match for deletion
        postgres_db_host: Database host
        postgres_db_port: Database port
        postgres_db_dbname: Database name
        postgres_db_user: Database user
        postgres_db_password: Database password (optional for cert-based auth)
        postgres_sslmode: SSL mode - one of: disable, allow, prefer,
                                     require, verify-ca, verify-full
        postgres_sslcert: Client certificate content as string (for mTLS)
        postgres_sslkey: Client private key content as string (for mTLS)
        postgres_sslrootcert: CA certificate content as string (for mTLS)
        postgres_sslpassword: SSL Key password
        autocommit: Whether to autocommit the transaction (default: True)

    Returns:
        Dictionary with table names as keys and number of deleted
        rows as values. Returns empty dict if cleanup fails.

    Note:
        When certificate/key content is provided, temporary files are created
        automatically and cleaned up when the function completes.
        This function catches all psycopg exceptions and logs them without
        re-raising, as it's part of cleanup and should not block other cleanup
        operations.

    """
    tables = [
        "drools_ansible_action_info",
        "drools_ansible_ha_stats",
        "drools_ansible_matching_event",
        "drools_ansible_session_state",
    ]

    results = {}

    try:
        # Create temporary cert files if content provided
        with _temp_cert_files(
            sslcert_content=postgres_sslcert,
            sslkey_content=postgres_sslkey,
            sslrootcert_content=postgres_sslrootcert,
        ) as (sslcert_path, sslkey_path, sslrootcert_path):
            conn_params = _build_connection_params(
                postgres_db_host,
                postgres_db_port,
                postgres_db_name,
                postgres_db_user,
                postgres_sslmode,
                postgres_db_password,
                postgres_sslpassword,
                sslcert_path,
                sslkey_path,
                sslrootcert_path,
            )

            with psycopg.connect(**conn_params, autocommit=autocommit) as conn:
                with conn.cursor() as cur:
                    for table in tables:
                        if _table_exists(cur, table):
                            results[table] = _delete_from_table(
                                cur, table, ha_uuid
                            )
                        else:
                            LOGGER.warning(
                                "Table %s does not exist, skipping deletion",
                                table,
                            )
                            results[table] = 0

                    # If not autocommit, commit manually
                    if not autocommit:
                        conn.commit()

    except psycopg.Error as e:
        LOGGER.error(
            "Error during Drools cleanup for ha_uuid %s: %s",
            ha_uuid,
            str(e),
            exc_info=True,
        )
        # Return empty results dict to indicate cleanup failed
        # but don't re-raise to allow other cleanup operations to continue

    return results


def drools_cleanup(obj: Activation):
    cred = obj.rule_engine_credential or get_default_rule_engine_credential()
    if cred:
        LOGGER.info(
            "Deleting Drools persistence information for Activation %d",
            obj.id,
        )
        inputs = get_resolved_secrets(cred)

        # Filter inputs to only include parameters accepted by
        # _delete_rows_by_ha_uuid
        valid_params = {
            "postgres_db_host",
            "postgres_db_port",
            "postgres_db_name",
            "postgres_db_user",
            "postgres_db_password",
            "postgres_sslmode",
            "postgres_sslcert",
            "postgres_sslkey",
            "postgres_sslpassword",
            "postgres_sslrootcert",
            "autocommit",
        }
        filtered_inputs = {
            k: v for k, v in inputs.items() if k in valid_params
        }

        result = _delete_rows_by_ha_uuid(str(obj.id), **filtered_inputs)
        LOGGER.info(
            "Deleted Drools data for Activation %d : %s",
            obj.id,
            str(result),
        )
