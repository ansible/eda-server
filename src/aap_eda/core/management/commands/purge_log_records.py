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

from argparse import ArgumentTypeError
from datetime import datetime, time, timezone
from uuid import UUID

from django.core.management.base import (
    BaseCommand,
    CommandError,
    CommandParser,
)

from aap_eda.core.utils.delete_log_util import (
    LogPurgeError,
    delete_logs_older_than,
)
from aap_eda.core.utils.log_retention import retention_cutoff


class Command(BaseCommand):
    """Purge old logs globally or for selected activations."""

    help = (
        "Purge log records older than exactly one cutoff, or use "
        "--purge-all-logs to replace every existing log with an audit "
        "marker. Without activation "
        "selectors, include every process (including orphaned processes). "
        "Activation IDs and names limit deletion to their union. "
        "One audit marker per affected process is enabled by default."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--activation-ids",
            nargs="+",
            type=int,
            dest="activation-ids",
            help=("Limit deletion to these activation IDs (e.g., 123 456)."),
        )
        parser.add_argument(
            "--activation-names",
            nargs="+",
            type=str,
            dest="activation-names",
            help=(
                "Limit deletion to these activation names (e.g., "
                "ActivationName1 ActivationName2)."
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
            "--purge-all-logs",
            dest="purge-all-logs",
            action="store_true",
            help=(
                "Delete all existing process logs at every timestamp, "
                "including earlier audit markers, and leave one new audit "
                "marker per affected process. Cannot be combined with a "
                "cutoff, activation selectors, or --audit-trail=false."
            ),
        )
        parser.add_argument(
            "--audit-trail",
            dest="audit_trail",
            type=self._audit_trail_value,
            default=True,
            metavar="true|false",
            help="Create a marker for each affected process (default: true).",
        )
        parser.add_argument(
            "--internal-job-uuid",
            dest="internal-job-uuid",
            default=None,
            help="EDA purge task UUID to include in audit markers.",
        )

    @staticmethod
    def _audit_trail_value(value: str) -> bool:
        if value == "true":
            return True
        if value == "false":
            return False
        raise ArgumentTypeError("--audit-trail must be true or false.")

    @staticmethod
    def _cutoff(options: dict) -> datetime:
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

        raise CommandError(
            "Exactly one of --date or --retention-duration is required."
        )

    def handle(self, *args, **options):
        ids = options.get("activation-ids")
        names = options.get("activation-names")
        purge_all_logs = options.get("purge-all-logs", False)
        if not isinstance(purge_all_logs, bool):
            raise CommandError("--purge-all-logs must be a boolean flag.")
        if purge_all_logs and (
            options.get("date") is not None
            or options.get("retention_duration") is not None
            or ids is not None
            or names is not None
        ):
            raise CommandError(
                "--purge-all-logs cannot be combined with a cutoff or "
                "activation selectors."
            )
        cutoff = None if purge_all_logs else self._cutoff(options)
        if cutoff is not None and cutoff > datetime.now(timezone.utc):
            raise CommandError("--date must not be in the future.")
        job_uuid = options.get("internal-job-uuid")
        if job_uuid is not None:
            try:
                job_uuid = str(UUID(str(job_uuid)))
            except (TypeError, ValueError, AttributeError) as exc:
                raise CommandError(
                    "--internal-job-uuid must be a UUID."
                ) from exc
        audit_trail = options["audit_trail"]
        if isinstance(audit_trail, str):
            try:
                audit_trail = self._audit_trail_value(audit_trail)
            except ArgumentTypeError as exc:
                raise CommandError(str(exc)) from exc
        elif not isinstance(audit_trail, bool):
            raise CommandError("--audit-trail must be true or false.")
        if purge_all_logs and not audit_trail:
            raise CommandError("--purge-all-logs requires audit trail.")

        try:
            deleted_count = delete_logs_older_than(
                cutoff,
                activation_ids=ids,
                activation_names=names,
                audit_trail=audit_trail,
                internal_job_uuid=job_uuid,
                purge_all_logs=purge_all_logs,
            )
        except (LogPurgeError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        if purge_all_logs:
            marker_result = (
                "Created audit markers for affected processes."
                if deleted_count
                else "No audit markers created."
            )
            return self.style.SUCCESS(
                f"Purged {deleted_count} log records globally at all "
                f"timestamps. {marker_result}"
            )

        scope = (
            "globally"
            if ids is None and names is None
            else "for selected activations"
        )
        return self.style.SUCCESS(
            f"Purged {deleted_count} log records older than "
            f"{cutoff.strftime('%Y-%m-%d %H:%M:%S UTC')} {scope}."
        )
