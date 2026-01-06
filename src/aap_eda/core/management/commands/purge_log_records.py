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

from datetime import datetime

from django.core.management.base import (
    BaseCommand,
    CommandError,
    CommandParser,
)
from django.db import transaction
from django.db.models import Q

from aap_eda.core import models


class Command(BaseCommand):
    """Purge the logs from a rulebook process."""

    help = (
        "Purge log records from rulebook processes. "
        "Always purges ALL log records older than the cutoff date globally. "
        "If activation ids or names are specified, detailed reporting is "
        "provided for those activations and orphaned records."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--activation-ids",
            nargs="+",
            type=int,
            dest="activation-ids",
            help=(
                "Specify the activation ids which you want to clear their "
                "records (e.g., ActivationID1 ActivationID2)"
            ),
        )
        parser.add_argument(
            "--activation-names",
            nargs="+",
            type=str,
            dest="activation-names",
            help=(
                "Specify the activation names which you want to clear their "
                "records (e.g., ActivationName1 ActivationName2)"
            ),
        )
        parser.add_argument(
            "--date",
            dest="date",
            action="store",
            required=True,
            help=(
                "Purge records older than this date from the database. "
                "The cutoff date in YYYY-MM-DD format"
            ),
        )

    def purge_log_records(
        self, ids: list[int], names: list[str], cutoff_timestamp: datetime
    ) -> None:
        # Global purge of all old logs (regardless of activation)
        cutoff_ts = int(cutoff_timestamp.timestamp())
        old_logs = models.RulebookProcessLog.objects.filter(
            log_timestamp__lt=cutoff_ts
        )
        deleted_count = old_logs.count()

        if deleted_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"No log records found older than "
                    f"{cutoff_timestamp.strftime('%Y-%m-%d')}."
                )
            )
            return

        # Delete all old logs globally
        old_logs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Purged {deleted_count} log records older than "
                f"{cutoff_timestamp.strftime('%Y-%m-%d')} globally."
            )
        )

        # Create audit trail logs for reporting
        audit_logs = []

        if not bool(ids) and not bool(names):
            # No filters: Create audit logs for all instances that might
            # have been affected
            instances = models.RulebookProcess.objects.all()
        else:
            # Filters provided: Create audit logs only for specified
            # activations and orphaned records
            instances = models.RulebookProcess.objects.filter(
                Q(activation__id__in=ids)
                | Q(activation__name__in=names)
                | Q(activation__isnull=True),
            )

            # Report on orphaned records for user visibility
            orphaned_count = models.RulebookProcess.objects.filter(
                activation__isnull=True
            ).count()
            if orphaned_count > 0:
                self.stdout.write(
                    f"Audit trail will include {orphaned_count} orphaned "
                    f"RulebookProcess records (with NULL activation)."
                )

        # Create audit trail logs for instances
        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for instance in instances:
            audit_logs.append(
                models.RulebookProcessLog(
                    log=(
                        f"All log records older than "
                        f"{cutoff_timestamp.strftime('%Y-%m-%d')} "
                        f"were purged at {dt}."
                    ),
                    activation_instance_id=instance.id,
                    log_timestamp=cutoff_ts,
                )
            )

        if audit_logs:
            models.RulebookProcessLog.objects.bulk_create(audit_logs)
            self.stdout.write(
                f"Created {len(audit_logs)} audit trail log entries."
            )

    @transaction.atomic
    def handle(self, *args, **options):
        input_ids = options.get("activation-ids") or []
        input_names = options.get("activation-names") or []
        cutoff_date = options.get("date")

        try:
            ts = datetime.strptime(cutoff_date, "%Y-%m-%d")
        except ValueError as e:
            raise CommandError(f"{e}") from e

        self.purge_log_records(
            ids=input_ids, names=input_names, cutoff_timestamp=ts
        )
