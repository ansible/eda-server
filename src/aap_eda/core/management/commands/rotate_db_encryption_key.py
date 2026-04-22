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

r"""Re-encrypt all EncryptedTextField columns after changing SECRET_KEY.

Mirrors the operational pattern of ``awx-manage regenerate_secret_key``
(Automation Controller): stop traffic, run the command, update the
deployment secret with the new key, then restart services.

Usage::

    aap-eda-manage rotate_db_encryption_key
    EDA_SECRET_KEY='...' \
      aap-eda-manage rotate_db_encryption_key --use-custom-key
"""

from __future__ import annotations

import base64
import os
from typing import Iterator

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from aap_eda.core.utils.crypto.fields import (
    EncryptedTextField,
    decrypt_string,
    encrypt_string,
)

_ENCRYPTED_MARKER = "$encrypted$"
_FETCH_BATCH_SIZE = 2000


def _iter_encrypted_text_fields() -> Iterator[tuple[type, EncryptedTextField]]:
    """Yield ``(model_class, field)`` for every EncryptedTextField.

    Only yields fields defined directly on the model (not inherited)
    to avoid processing the same column twice in multi-table
    inheritance hierarchies.
    """
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if (
                isinstance(field, EncryptedTextField)
                and getattr(field, "model", None) is model
            ):
                yield model, field


class Command(BaseCommand):
    """Re-encrypt every secret in the database with a new SECRET_KEY.

    Modelled after ``awx-manage regenerate_secret_key``: the entire
    re-encryption runs inside a single database transaction so that a
    failure at any point rolls back all changes automatically.

    Unlike the AWX counterpart, encrypted columns are discovered
    dynamically via ``EncryptedTextField`` introspection rather than a
    static model list, so newly added encrypted fields are covered
    without updating this command.
    """

    help = (
        "Re-encrypt database values for all EncryptedTextField columns "
        "after rotating SECRET_KEY."
    )

    def add_arguments(self, parser):
        """Define CLI arguments for the command."""
        parser.add_argument(
            "--use-custom-key",
            dest="use_custom_key",
            action="store_true",
            default=False,
            help=(
                "Use the key from the EDA_SECRET_KEY environment "
                "variable instead of generating a new one."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report affected rows without writing to the database.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        """Run the re-encryption inside an atomic transaction."""
        use_custom_key: bool = options["use_custom_key"]
        dry_run: bool = options["dry_run"]

        self.old_key = settings.SECRET_KEY

        if use_custom_key:
            self.new_key = os.environ.get("EDA_SECRET_KEY")
            if not self.new_key:
                raise CommandError(
                    "--use-custom-key was specified but "
                    "EDA_SECRET_KEY is not set in the environment."
                )
        else:
            self.new_key = base64.encodebytes(os.urandom(33)).decode().rstrip()

        if self.new_key == self.old_key:
            raise CommandError(
                "New encryption key is identical to the current "
                "SECRET_KEY; rotation aborted."
            )

        fields = list(_iter_encrypted_text_fields())
        total = self._reencrypt_fields(fields, dry_run)

        if dry_run:
            self.stdout.write(f"{total} value(s) would be re-encrypted.")
        else:
            self.stdout.write(f"{total} value(s) re-encrypted.")

        if not use_custom_key:
            self.stdout.write(self.new_key)

    def _reencrypt_fields(self, fields, dry_run: bool) -> int:
        """Decrypt with old key, re-encrypt with new key.

        Rows are fetched in batches of ``_FETCH_BATCH_SIZE`` to avoid
        loading the entire table into memory.  Identifiers are quoted
        via ``connection.ops.quote_name`` for backend portability.

        Exceptions from decrypt/encrypt are intentionally not caught
        so they propagate and trigger the ``@transaction.atomic``
        rollback, matching ``awx-manage regenerate_secret_key``
        behaviour.
        """
        total = 0
        for model, field in fields:
            total += self._reencrypt_column(model, field, dry_run)
        return total

    @staticmethod
    def _build_select_page_sql(model, field) -> str:
        """Build a paginated SELECT for encrypted column scanning.

        Uses PK-window pagination (``WHERE pk > %s ORDER BY pk LIMIT n``)
        so only one page of rows is buffered by the database driver at a
        time, regardless of table size.

        Safe from SQL injection: all identifiers originate from Django
        model metadata and are quoted via the database backend.
        """
        qn = connection.ops.quote_name
        return (
            "SELECT {pk}, {col} FROM {table} "
            "WHERE {col} IS NOT NULL AND {pk} > %s "
            "ORDER BY {pk} LIMIT {limit}"
        ).format(
            pk=qn(model._meta.pk.column),
            col=qn(field.column),
            table=qn(model._meta.db_table),
            limit=_FETCH_BATCH_SIZE,
        )

    @staticmethod
    def _build_update_sql(model, field) -> str:
        """Build an UPDATE query for re-encrypting a single row.

        Safe from SQL injection: all identifiers originate from Django
        model metadata and are quoted via the database backend.
        """
        qn = connection.ops.quote_name
        return "UPDATE {table} SET {col} = %s WHERE {pk} = %s".format(
            table=qn(model._meta.db_table),
            col=qn(field.column),
            pk=qn(model._meta.pk.column),
        )

    def _reencrypt_column(self, model, field, dry_run: bool) -> int:
        """Re-encrypt a single column across all rows."""
        select_sql = self._build_select_page_sql(model, field)
        update_sql = self._build_update_sql(model, field)
        count = 0
        last_pk = 0
        while True:
            with connection.cursor() as cur:
                cur.execute(select_sql, [last_pk])
                rows = cur.fetchall()
            if not rows:
                break
            last_pk = rows[-1][0]
            count += self._reencrypt_rows(rows, update_sql, dry_run)
        return count

    def _reencrypt_rows(self, rows, update_sql, dry_run):
        """Decrypt and re-encrypt a batch of rows."""
        count = 0
        for pk, raw in rows:
            if not raw or _ENCRYPTED_MARKER not in str(raw):
                continue
            clear = decrypt_string(raw, key_material=self.old_key)
            new_val = encrypt_string(clear, key_material=self.new_key)
            if not dry_run:
                with connection.cursor() as ucur:
                    ucur.execute(update_sql, [new_val, pk])
            count += 1
        return count
