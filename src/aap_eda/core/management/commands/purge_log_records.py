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

from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import (
    BaseCommand,
    CommandError,
    CommandParser,
)
from django.db import transaction
from django.utils import timezone

from aap_eda.core.utils.delete_log_util import (
    create_audit_trail,
    delete_logs_older_than,
)


class Command(BaseCommand):
    """Purge the logs from a rulebook process."""

    help = (
        "Purge log records from rulebook processes. "
        "Uses --date for a specific cutoff or defaults to "
        "ACTIVATION_DB_LOG_RETENTION_DAYS. Use --audit-trail to record "
        "the purge in activation logs."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--activation-ids",
            nargs="+",
            type=int,
            dest="activation-ids",
            help=(
                "Scope audit trail to these activation ids "
                "(e.g., 1 2 3). Only used with --audit-trail."
            ),
        )
        parser.add_argument(
            "--activation-names",
            nargs="+",
            type=str,
            dest="activation-names",
            help=(
                "Scope audit trail to these activation names "
                "(e.g., name1 name2). Only used with --audit-trail."
            ),
        )
        parser.add_argument(
            "--date",
            dest="date",
            action="store",
            help=(
                "Purge records older than this date (YYYY-MM-DD). "
                "Defaults to ACTIVATION_DB_LOG_RETENTION_DAYS if omitted."
            ),
        )
        parser.add_argument(
            "--audit-trail",
            dest="audit_trail",
            action="store_true",
            default=False,
            help="Create audit trail log entries recording the purge.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        cutoff_date = options.get("date")

        if cutoff_date:
            try:
                cutoff = timezone.make_aware(
                    datetime.strptime(cutoff_date, "%Y-%m-%d")
                )
            except ValueError as e:
                raise CommandError(f"{e}") from e
        else:
            retention_days = settings.ACTIVATION_DB_LOG_RETENTION_DAYS
            if retention_days <= 0:
                self.stdout.write(
                    "ACTIVATION_DB_LOG_RETENTION_DAYS is 0; nothing to purge."
                )
                return
            cutoff = timezone.now() - timedelta(days=retention_days)

        deleted = delete_logs_older_than(cutoff)

        if deleted == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"No log records found older than "
                    f"{cutoff.strftime('%Y-%m-%d')}."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Purged {deleted} log records older than "
                f"{cutoff.strftime('%Y-%m-%d')} globally."
            )
        )

        if options.get("audit_trail"):
            ids = options.get("activation-ids") or []
            names = options.get("activation-names") or []
            count = create_audit_trail(
                cutoff,
                activation_ids=ids,
                activation_names=names,
            )
            self.stdout.write(f"Created {count} audit trail log entries.")
