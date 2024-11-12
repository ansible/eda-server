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
from typing import Union

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
        "If activation ids or names are not specified, "
        "all log records older than the cutoff date will be purged."
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
        new_instance_logs = []
        if not bool(ids) and not bool(names):
            instances = models.RulebookProcess.objects.all()
        else:
            instances = models.RulebookProcess.objects.filter(
                Q(activation__id__in=ids) | Q(activation__name__in=names),
            )

        if not instances.exists():
            self.stdout.write(
                self.style.SUCCESS("No records has been found for purging.")
            )
            return

        for instance in instances:
            new_instance_logs.append(
                self.clean_instance_logs(instance, cutoff_timestamp)
            )

        new_instance_logs = [
            item for item in new_instance_logs if item is not None
        ]
        if len(new_instance_logs) > 0:
            models.RulebookProcessLog.objects.bulk_create(new_instance_logs)

            self.stdout.write(
                self.style.SUCCESS(
                    "Log records older than "
                    f"{cutoff_timestamp.strftime('%Y-%m-%d')} are purged."
                )
            )

    def clean_instance_logs(
        self,
        instance: models.RulebookProcess,
        cutoff_timestamp: datetime,
    ) -> Union[models.RulebookProcessLog, None]:
        log_records = models.RulebookProcessLog.objects.filter(
            activation_instance=instance,
            log_timestamp__lt=int(cutoff_timestamp.timestamp()),
        )
        if not log_records.exists():
            return

        log_records.delete()
        dt = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        return models.RulebookProcessLog(
            log=(
                "All log records older than "
                f"{cutoff_timestamp.strftime('%Y-%m-%d')} are purged at {dt}."
            ),
            activation_instance_id=instance.id,
            log_timestamp=int(cutoff_timestamp.timestamp()),
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
