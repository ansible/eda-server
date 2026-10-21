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

from datetime import datetime, time, timedelta, timezone

from django.conf import settings
from django.core.management.base import (
    BaseCommand,
    CommandError,
    CommandParser,
)

from aap_eda.core.utils.delete_log_util import (
    LogPurgeError,
    create_audit_trail,
    delete_logs_older_than,
)
from aap_eda.core.utils.log_retention import retention_cutoff


class Command(BaseCommand):
    """Purge old logs globally, optionally writing audit trail entries."""

    help = (
        "Purge log records from rulebook processes. "
        "Always purges all log records older than --date globally. "
        "Activation ids or names only control detailed reporting for those "
        "activations and orphaned records; they do not limit deletion."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--activation-ids",
            nargs="+",
            type=int,
            dest="activation-ids",
            help=(
                "Activation ids to include in detailed reporting only. "
                "This does not limit deletion: all log records older than "
                "--date are purged globally (e.g., 123 456)."
            ),
        )
        parser.add_argument(
            "--activation-names",
            nargs="+",
            type=str,
            dest="activation-names",
            help=(
                "Activation names to include in detailed reporting only. "
                "This does not limit deletion: all log records older than "
                "--date are purged globally (e.g., ActivationName1 "
                "ActivationName2)."
            ),
        )
        parser.add_argument(
            "--date",
            dest="date",
            action="store",
            help=(
                "Purge records older than this date from the database. "
                "The UTC cutoff date in YYYY-MM-DD format. Mutually exclusive "
                "with --retention-duration."
            ),
        )

        parser.add_argument(
            "--retention-duration",
            dest="retention_duration",
            help=(
                "Purge records older than this ISO 8601 duration, for "
                "example P30D or P1M. Mutually exclusive with --date."
            ),
        )
        parser.add_argument(
            "--audit-trail",
            dest="audit_trail",
            action="store_true",
            help="Create audit log entries for affected processes.",
        )

    @staticmethod
    def _cutoff(options: dict) -> datetime | None:
        cutoff_date = options.get("date")
        retention_duration = options.get("retention_duration")
        if cutoff_date is not None and retention_duration is not None:
            raise CommandError(
                "--date and --retention-duration are mutually exclusive."
            )

        if cutoff_date is not None:
            try:
                parsed_date = datetime.strptime(cutoff_date, "%Y-%m-%d").date()
            except (TypeError, ValueError) as exc:
                raise CommandError(
                    "--date must use YYYY-MM-DD format."
                ) from exc
            if parsed_date.strftime("%Y-%m-%d") != cutoff_date:
                raise CommandError("--date must use YYYY-MM-DD format.")
            return datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)

        if retention_duration is not None:
            try:
                return retention_cutoff(retention_duration)
            except ValueError as exc:
                raise CommandError(str(exc)) from exc

        retention_days = settings.ACTIVATION_DB_LOG_RETENTION_DAYS
        if retention_days <= 0:
            return None
        return datetime.now(timezone.utc) - timedelta(days=retention_days)

    def handle(self, *args, **options):
        ids = options.get("activation-ids") or []
        names = options.get("activation-names") or []
        if any(activation_id <= 0 for activation_id in ids):
            raise CommandError("Activation IDs must be positive integers.")
        if any(not name.strip() for name in names):
            raise CommandError("Activation names cannot be blank.")

        cutoff = self._cutoff(options)
        if cutoff is None:
            return self.style.WARNING(
                "No logs purged: configured retention is not positive."
            )

        try:
            deleted_count = delete_logs_older_than(cutoff)
        except LogPurgeError as exc:
            raise CommandError(str(exc)) from exc

        if deleted_count == 0:
            return self.style.SUCCESS(
                f"No log records found older than "
                f"{cutoff.strftime('%Y-%m-%d %H:%M:%S UTC')}; 0 rows "
                "deleted."
            )

        output = (
            f"Purged {deleted_count} log records older than "
            f"{cutoff.strftime('%Y-%m-%d %H:%M:%S UTC')} globally."
        )
        if options.get("audit_trail"):
            try:
                audit_count = create_audit_trail(
                    cutoff,
                    activation_ids=ids,
                    activation_names=names,
                )
            except Exception as exc:
                raise CommandError(
                    f"Deleted {deleted_count} logs, but audit trail failed: "
                    f"{exc}"
                ) from exc
            output += f" Created {audit_count} audit trail entries."
        return self.style.SUCCESS(output)
