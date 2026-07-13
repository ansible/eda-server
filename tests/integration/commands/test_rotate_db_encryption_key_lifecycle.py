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

"""Integration tests for rotate_db_encryption_key.

These tests run the management command via subprocess so that
dynaconf loads settings from environment variables — the same
path used in production. Unit tests bypass this by setting
settings.SECRET_KEY directly.

Skipped by default. Run via the dedicated task command::

    task test:rotate-db-encryption-key

Or run a specific test class::

    task test:rotate-db-encryption-key -- \
        -k "TestRotateDbEncryptionKeyLifecycle"
    task test:rotate-db-encryption-key -- \
        -k "TestRotateDbEncryptionKeyService"

Prerequisites:
    - Command-level tests: Postgres running (``task docker:up:minimal``)
    - Service-level tests: full Docker stack started with an explicit key::

          EDA_SECRET_KEY=insecure task docker:up

      Do NOT use bare ``task docker:up`` — the docker-compose-dev.yaml
      default adds literal quotes around the key value, causing a
      mismatch when the test restarts services during rotation.
    - Service-level tests require ``docker compose up -d`` to work
      (the test restarts containers mid-rotation). If the restart
      fails, the DB is left encrypted with a rotated key that no
      running service knows — see recovery steps below.

Recovery from a failed service-level test::

    task docker:purge && EDA_SECRET_KEY=insecure task docker:up

See also:
    - AGENTS.md § "Manual Validation: DB Encryption Key Rotation"
    - docs/development.md (for developer-facing documentation)
    - Taskfile.dist.yaml ``test:rotate-db-encryption-key`` task
"""

import os
import subprocess
import time

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_ROTATION_TESTS"),
    reason=(
        "Manual test: set RUN_ROTATION_TESTS=1"
        " to run against a live database"
    ),
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EDA_API_CONTAINER = os.environ.get("EDA_API_CONTAINER", "eda-eda-api-1")
EDA_API_URL = os.environ.get("EDA_API_URL", "http://localhost:8000")


def _check_docker_connectivity() -> None:
    """Fail fast if docker compose is not reachable."""
    result = subprocess.run(
        ["docker", "compose", "version"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Service-level rotation tests require "
            "'docker compose up -d' to restart containers mid-test. "
            "If the DB is in a corrupted state from a previous "
            "failed run, recover with: "
            "task docker:purge && EDA_SECRET_KEY=insecure task docker:up"
        )


def _run_manage(
    args: list[str], env: dict | None = None
) -> subprocess.CompletedProcess:
    cmd_env = os.environ.copy()
    if env:
        cmd_env.update(env)
    return subprocess.run(
        ["aap-eda-manage", *args],
        env=cmd_env,
        capture_output=True,
        text=True,
    )


def _run_shell(script: str, env: dict | None = None) -> str:
    result = _run_manage(["shell", "-c", script], env=env)
    assert result.returncode == 0, f"shell command failed: {result.stderr}"
    return result.stdout.strip()


def _docker_exec(
    cmd: str, env: dict | None = None
) -> subprocess.CompletedProcess:
    env_args: list[str] = []
    if env:
        for k, v in env.items():
            env_args.extend(["-e", f"{k}={v}"])
    return subprocess.run(
        [
            "docker",
            "exec",
            *env_args,
            EDA_API_CONTAINER,
            "bash",
            "-c",
            cmd,
        ],
        capture_output=True,
        text=True,
    )


def _docker_restart_all(new_key: str) -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            "eda",
            "-f",
            "tools/docker/docker-compose-dev.yaml",
            "up",
            "-d",
        ],
        env={**os.environ, "EDA_SECRET_KEY": new_key},
        capture_output=True,
        text=True,
        check=True,
    )
    _wait_for_api()


def _wait_for_api(timeout: int = 60) -> None:
    import requests

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{EDA_API_URL}/_healthz", timeout=5)
            if r.status_code == 200:
                return
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ):
            pass
        time.sleep(2)
    raise TimeoutError(f"EDA API did not become healthy within {timeout}s")


# ---------------------------------------------------------------------------
# Command-level lifecycle tests (Postgres only)
# ---------------------------------------------------------------------------


class TestRotateDbEncryptionKeyLifecycle:
    """Full lifecycle: create, rotate, verify, restore.

    Tests both Setting (simple string) and EdaCredential (JSON inputs)
    to verify rotation works across different EncryptedTextField models.
    """

    TEST_KEY = "rotation_integration_test"
    TEST_VALUE = "integration-test-secret-value"
    CRED_NAME = "rotation-integration-test-cred"
    CRED_INPUTS = '{"username": "testuser", "password": "s3cret!"}'

    def _create_test_data(self):
        _run_shell(
            "from aap_eda.core.models import Setting\n"
            f"Setting.objects.filter(key='{self.TEST_KEY}').delete()\n"
            f"Setting.objects.create(key='{self.TEST_KEY}', "
            f"value='{self.TEST_VALUE}')"
        )
        _run_shell(
            "from aap_eda.core.models import ("
            "EdaCredential, CredentialType, Organization)\n"
            f"EdaCredential.objects.filter("
            f"name='{self.CRED_NAME}').delete()\n"
            f"EdaCredential.objects.create("
            f"name='{self.CRED_NAME}', "
            f"inputs='{self.CRED_INPUTS}', "
            "credential_type=CredentialType.objects.get(id=1), "
            "organization=Organization.objects.first())"
        )

    def _cleanup_test_data(self, env: dict | None = None):
        _run_shell(
            "from aap_eda.core.models import Setting\n"
            f"Setting.objects.filter(key='{self.TEST_KEY}').delete()",
            env=env,
        )
        _run_shell(
            "from aap_eda.core.models import EdaCredential\n"
            f"EdaCredential.objects.filter("
            f"name='{self.CRED_NAME}').delete()",
            env=env,
        )

    def _verify_decrypted_values(self, env: dict | None = None):
        tag_setting = "DECRYPTED_SETTING="
        tag_cred = "DECRYPTED_CRED="
        output = _run_shell(
            "from aap_eda.core.models import Setting, EdaCredential\n"
            f"s = Setting.objects.get(key='{self.TEST_KEY}')\n"
            f"print('{tag_setting}' + s.value.get_secret_value())\n"
            f"c = EdaCredential.objects.get("
            f"name='{self.CRED_NAME}')\n"
            f"print('{tag_cred}' + c.inputs.get_secret_value())",
            env=env,
        )
        results = {}
        for line in output.splitlines():
            if line.startswith(tag_setting):
                results["SETTING"] = line[len(tag_setting) :]
            elif line.startswith(tag_cred):
                results["CRED"] = line[len(tag_cred) :]

        assert (
            results.get("SETTING") == self.TEST_VALUE
        ), f"Setting mismatch: {results.get('SETTING')!r}"
        assert (
            results.get("CRED") == self.CRED_INPUTS
        ), f"Credential mismatch: {results.get('CRED')!r}"

    def test_full_lifecycle_with_auto_generated_key(self):
        """Create data, rotate, verify decryption, rotate back."""
        original_key = os.environ.get("EDA_SECRET_KEY")
        assert original_key, "EDA_SECRET_KEY must be set"

        self._create_test_data()
        new_key = None

        try:
            result = _run_manage(["rotate_db_encryption_key"])
            assert result.returncode == 0, result.stderr
            assert "re-encrypted" in result.stdout

            lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
            assert (
                len(lines) >= 2
            ), f"Expected count + key in output: {result.stdout}"
            new_key = lines[-1]

            self._verify_decrypted_values(
                env={"EDA_SECRET_KEY": new_key},
            )

        finally:
            if new_key:
                restore = _run_manage(
                    [
                        "rotate_db_encryption_key",
                        "--use-custom-key",
                    ],
                    env={
                        "EDA_SECRET_KEY": new_key,
                        "EDA_DB_ROTATION_KEY": original_key,
                    },
                )
                if restore.returncode != 0:
                    raise RuntimeError(
                        "Failed to restore original key: " f"{restore.stderr}"
                    )
            self._cleanup_test_data()

    def test_full_lifecycle_with_custom_key(self):
        """Create data, rotate with custom key, verify, rotate back."""
        original_key = os.environ.get("EDA_SECRET_KEY")
        assert original_key, "EDA_SECRET_KEY must be set"
        custom_key = "integration-test-custom-rotation-key"
        rotated = False

        self._create_test_data()

        try:
            result = _run_manage(
                [
                    "rotate_db_encryption_key",
                    "--use-custom-key",
                ],
                env={"EDA_DB_ROTATION_KEY": custom_key},
            )
            assert result.returncode == 0, result.stderr
            assert "re-encrypted" in result.stdout
            rotated = True

            self._verify_decrypted_values(
                env={"EDA_SECRET_KEY": custom_key},
            )

        finally:
            if rotated:
                restore = _run_manage(
                    [
                        "rotate_db_encryption_key",
                        "--use-custom-key",
                    ],
                    env={
                        "EDA_SECRET_KEY": custom_key,
                        "EDA_DB_ROTATION_KEY": original_key,
                    },
                )
                if restore.returncode != 0:
                    raise RuntimeError(
                        "Failed to restore original key: " f"{restore.stderr}"
                    )
            self._cleanup_test_data()

    def test_dry_run_does_not_modify_data(self):
        """--dry-run reports rows but does not re-encrypt."""
        self._create_test_data()

        try:
            result = _run_manage(["rotate_db_encryption_key", "--dry-run"])
            assert result.returncode == 0, result.stderr
            assert "would be re-encrypted" in result.stdout

            self._verify_decrypted_values()

        finally:
            self._cleanup_test_data()


# ---------------------------------------------------------------------------
# Service-level lifecycle tests (full Docker stack)
# ---------------------------------------------------------------------------


class TestRotateDbEncryptionKeyService:
    """Verify the API works after key rotation and service restart.

    This tests the full operational workflow a customer would follow:
    create credentials, rotate the key, restart services with the
    new key, and verify the API still serves credentials correctly.
    """

    CRED_NAME = "rotation-service-test-cred"

    def _api_get(self, path: str) -> int:
        import requests

        r = requests.get(
            f"{EDA_API_URL}{path}",
            auth=("admin", "testpass"),
            timeout=10,
        )
        return r.status_code

    def _api_create_credential(self) -> int:
        import requests

        r = requests.post(
            f"{EDA_API_URL}/api/eda/v1/eda-credentials/",
            auth=("admin", "testpass"),
            json={
                "name": self.CRED_NAME,
                "credential_type_id": 1,
                "inputs": {
                    "username": "svc-test",
                    "password": "svc-test-pass",
                },
                "organization_id": 1,
            },
            timeout=10,
        )
        assert r.status_code == 201, f"Failed to create credential: {r.text}"
        return r.json()["id"]

    def _api_get_credential(self, cred_id: int) -> int:
        return self._api_get(f"/api/eda/v1/eda-credentials/{cred_id}/")

    def _cleanup(self, cred_id: int, env: dict | None = None):
        cmd = (
            "from aap_eda.core.models import EdaCredential; "
            f"EdaCredential.objects.filter(id={cred_id}).delete()"
        )
        _docker_exec(f'aap-eda-manage shell -c "{cmd}"', env=env)

    def _check_stale_credential(self):
        import requests

        r = requests.get(
            f"{EDA_API_URL}/api/eda/v1/eda-credentials/",
            auth=("admin", "testpass"),
            params={"name": self.CRED_NAME},
            timeout=10,
        )
        if r.status_code == 200 and r.json().get("count", 0) > 0:
            raise RuntimeError(
                f"Stale test credential '{self.CRED_NAME}' found from a "
                "previous failed run. The DB may be in an inconsistent "
                "state (key mismatch). Recover with:\n"
                "  task docker:purge && task docker:up"
            )

    def test_api_works_after_rotation_and_restart(self):
        """Full customer workflow: rotate, restart, verify API."""
        _check_docker_connectivity()
        _wait_for_api()
        self._check_stale_credential()

        result = _docker_exec("printenv EDA_SECRET_KEY")
        assert (
            result.returncode == 0
        ), "Cannot read EDA_SECRET_KEY from container"
        original_key = result.stdout.strip()

        cred_id = self._api_create_credential()
        new_key = None

        try:
            assert self._api_get_credential(cred_id) == 200

            # Rotate via docker exec
            result = _docker_exec("aap-eda-manage rotate_db_encryption_key")
            assert result.returncode == 0, result.stderr
            lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
            assert lines, f"Expected key in output: {result.stdout}"
            new_key = lines[-1]

            # API should fail — web service has old key
            assert self._api_get_credential(cred_id) == 500

            # Restart with new key
            _docker_restart_all(new_key)

            # API should work again
            assert self._api_get_credential(cred_id) == 200

        finally:
            if new_key:
                _docker_exec(
                    "aap-eda-manage rotate_db_encryption_key"
                    " --use-custom-key",
                    env={
                        "EDA_SECRET_KEY": new_key,
                        "EDA_DB_ROTATION_KEY": original_key,
                    },
                )
                _docker_restart_all(original_key)
            self._cleanup(cred_id)
