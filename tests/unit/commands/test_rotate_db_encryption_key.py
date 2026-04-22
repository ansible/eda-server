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

import io
import os
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from aap_eda.core.models import Setting
from aap_eda.core.utils.crypto.fields import decrypt_string


@pytest.mark.django_db
def test_use_custom_key_requires_eda_secret_key():
    """CommandError when --use-custom-key is set without EDA_SECRET_KEY."""
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("EDA_SECRET_KEY", None)
        with pytest.raises(CommandError, match="EDA_SECRET_KEY"):
            call_command("rotate_db_encryption_key", use_custom_key=True)


@pytest.mark.django_db
def test_same_key_aborts(settings):
    """CommandError when the new key equals the current SECRET_KEY."""
    settings.SECRET_KEY = "identical-key"
    with patch.dict(os.environ, {"EDA_SECRET_KEY": "identical-key"}):
        with pytest.raises(CommandError, match="identical"):
            call_command("rotate_db_encryption_key", use_custom_key=True)


@pytest.mark.django_db(transaction=True)
def test_dry_run_reports_without_writing(settings):
    """--dry-run reports affected rows but leaves ciphertext unchanged."""
    settings.SECRET_KEY = "test-secret-for-rotation-command"

    Setting.objects.create(key="dry_run_rotation", value="dry-run-secret")
    with connection.cursor() as cur:
        cur.execute(
            "SELECT value FROM core_setting WHERE key = %s",
            ["dry_run_rotation"],
        )
        old_cipher = cur.fetchone()[0]

    out = io.StringIO()
    with patch.dict(
        os.environ,
        {"EDA_SECRET_KEY": "new-secret-key-for-rotation"},
    ):
        call_command(
            "rotate_db_encryption_key",
            use_custom_key=True,
            dry_run=True,
            stdout=out,
        )

    assert "1 value(s) would be re-encrypted" in out.getvalue()

    with connection.cursor() as cur:
        cur.execute(
            "SELECT value FROM core_setting WHERE key = %s",
            ["dry_run_rotation"],
        )
        after_cipher = cur.fetchone()[0]
    assert after_cipher == old_cipher


@pytest.mark.django_db
def test_auto_generated_key_printed_once(settings):
    """Generated key appears exactly once in stdout."""
    settings.SECRET_KEY = "test-secret-for-auto-gen"
    out = io.StringIO()
    call_command(
        "rotate_db_encryption_key",
        dry_run=True,
        stdout=out,
    )
    lines = [ln for ln in out.getvalue().splitlines() if ln.strip()]
    assert lines[0].endswith("would be re-encrypted.")
    key_line = lines[1]
    assert len(key_line) > 0
    assert out.getvalue().count(key_line) == 1


@pytest.mark.django_db(transaction=True)
def test_reencryption_with_custom_key(settings):
    """Full rotation with custom key: ciphertext changes."""
    old_key = "old-rotation-test-key"
    new_key = "new-rotation-test-key"
    settings.SECRET_KEY = old_key

    Setting.objects.create(key="test_rotation", value="super-secret")

    with connection.cursor() as cur:
        cur.execute(
            "SELECT value FROM core_setting WHERE key = %s",
            ["test_rotation"],
        )
        old_cipher = cur.fetchone()[0]

    assert "$encrypted$" in old_cipher

    out = io.StringIO()
    with patch.dict(os.environ, {"EDA_SECRET_KEY": new_key}):
        call_command(
            "rotate_db_encryption_key",
            use_custom_key=True,
            stdout=out,
        )

    assert "1 value(s) re-encrypted" in out.getvalue()

    with connection.cursor() as cur:
        cur.execute(
            "SELECT value FROM core_setting WHERE key = %s",
            ["test_rotation"],
        )
        new_cipher = cur.fetchone()[0]

    assert new_cipher != old_cipher
    assert decrypt_string(new_cipher, key_material=new_key) == "super-secret"


@pytest.mark.django_db(transaction=True)
def test_reencryption_with_auto_generated_key(settings):
    """Full rotation with auto-generated key: new key is returned."""
    settings.SECRET_KEY = "old-key-for-auto-gen-test"

    Setting.objects.create(key="test_auto_rotate", value="secret-value")

    out = io.StringIO()
    call_command(
        "rotate_db_encryption_key",
        stdout=out,
    )

    output = out.getvalue()
    assert "1 value(s) re-encrypted." in output
    lines = [ln for ln in output.splitlines() if ln.strip()]
    new_key = lines[-1]

    with connection.cursor() as cur:
        cur.execute(
            "SELECT value FROM core_setting WHERE key = %s",
            ["test_auto_rotate"],
        )
        new_cipher = cur.fetchone()[0]

    assert decrypt_string(new_cipher, key_material=new_key) == "secret-value"
