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

import re
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
    purge_unattached_logs,
)
from aap_eda.core.utils.log_retention import retention_cutoff


class Command(BaseCommand):
    """Purge old logs globally or for selected activations."""

    help = (
        "Purge log records older than exactly one cutoff, or use "
        "--purge-all-logs with an optional cutoff to delete logs globally "
        "and leave one audit marker per affected process. Without activation "
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
                "Delete all existing process logs. When used alone, deletes "
                "every log at every timestamp. When combined with --date or "
                "--retention-duration, deletes logs older than the cutoff "
                "across all activations. Also deletes unattached logs "
                "(filtered by cutoff when provided). Cannot be combined "
                "with activation selectors or --audit-trail=false."
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
            help=(
                "Purge job UUID or custom ID (1-128 letters, digits, periods, "
                "underscores, or hyphens) to include in audit markers."
            ),
        )

    @staticmethod
    def _audit_trail_value(value: str) -> bool:
        """Parse audit-trail CLI flag to boolean."""
        if value == "true":
            return True
        if value == "false":
            return False
        raise ArgumentTypeError("--audit-trail must be true or false.")

    @staticmethod
    def _cutoff(options: dict) -> datetime:
        """Parse and validate cutoff date from CLI options."""
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

    def _purge_mode(self, options: dict) -> tuple[bool, datetime | None]:
        """Resolve and validate the purge scope and cutoff from CLI options."""
        ids = options.get("activation-ids")
        names = options.get("activation-names")
        purge_all_logs = options.get("purge-all-logs", False)
        if not isinstance(purge_all_logs, bool):
            raise CommandError("--purge-all-logs must be a boolean flag.")
        if purge_all_logs and (ids is not None or names is not None):
            raise CommandError(
                "--purge-all-logs cannot be combined with "
                "activation selectors."
            )
        has_cutoff = (
            options.get("date") is not None
            or options.get("retention_duration") is not None
        )
        if purge_all_logs and not has_cutoff:
            cutoff = None
        elif has_cutoff:
            cutoff = self._cutoff(options)
        else:
            raise CommandError(
                "Exactly one of --date, --retention-duration, or "
                "--purge-all-logs is required."
            )
        if cutoff is not None and cutoff > datetime.now(timezone.utc):
            raise CommandError("--date must not be in the future.")
        return purge_all_logs, cutoff

    def _validated_audit_trail(self, value, purge_all_logs: bool) -> bool:
        """Coerce and validate the audit-trail flag."""
        if isinstance(value, str):
            try:
                value = self._audit_trail_value(value)
            except ArgumentTypeError as exc:
                raise CommandError(str(exc)) from exc
        elif not isinstance(value, bool):
            raise CommandError("--audit-trail must be true or false.")
        if purge_all_logs and not value:
            raise CommandError("--purge-all-logs requires audit trail.")
        return value

    @staticmethod
    def _delete_unattached_logs(
        deleted_count: int, cutoff_timestamp: float | None
    ) -> int:
        """Delete logs not linked to any activation instance."""
        try:
            deleted_count += purge_unattached_logs(cutoff_timestamp)
        except Exception as exc:
            raise LogPurgeError(
                f"Log purge failed after {deleted_count} committed rows: "
                f"{exc}",
                deleted_count=deleted_count,
            ) from exc
        return deleted_count

    @staticmethod
    def _validated_job_uuid(job_uuid):
        """Normalise a UUID or validate a custom job ID string."""
        if job_uuid is None:
            return None
        try:
            return str(UUID(str(job_uuid)))
        except (TypeError, ValueError, AttributeError) as exc:
            if not isinstance(job_uuid, str) or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", job_uuid
            ):
                raise CommandError(
                    "--internal-job-uuid must be a UUID or a custom ID "
                    "of 1-128 ASCII letters, digits, periods, "
                    "underscores, or hyphens, starting with a letter "
                    "or digit."
                ) from exc
        return job_uuid

    def handle(self, *args, **options):
        ids = options.get("activation-ids")
        names = options.get("activation-names")
        purge_all_logs, cutoff = self._purge_mode(options)
        job_uuid = self._validated_job_uuid(options.get("internal-job-uuid"))
        audit_trail = self._validated_audit_trail(
            options["audit_trail"], purge_all_logs
        )

        try:
            process_deleted_count = delete_logs_older_than(
                cutoff,
                activation_ids=ids,
                activation_names=names,
                audit_trail=audit_trail,
                internal_job_uuid=job_uuid,
                purge_all_logs=purge_all_logs,
            )
            if purge_all_logs:
                deleted_count = self._delete_unattached_logs(
                    process_deleted_count,
                    cutoff.timestamp() if cutoff is not None else None,
                )
        except (LogPurgeError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        if purge_all_logs:
            marker_result = (
                "Created audit markers for affected processes."
                if process_deleted_count
                else "No audit markers created."
            )
            noun = "record" if deleted_count == 1 else "records"
            if cutoff is not None:
                cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S UTC")
                return self.style.SUCCESS(
                    f"Purged {deleted_count} log {noun} globally older "
                    f"than {cutoff_str}. {marker_result}"
                )
            return self.style.SUCCESS(
                f"Purged {deleted_count} log {noun} globally at all "
                f"timestamps. {marker_result}"
            )

        noun = "record" if process_deleted_count == 1 else "records"
        scope = (
            "globally"
            if ids is None and names is None
            else "for selected activations"
        )
        return self.style.SUCCESS(
            f"Purged {process_deleted_count} log {noun} older than "
            f"{cutoff.strftime('%Y-%m-%d %H:%M:%S UTC')} {scope}."
        )
