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

from datetime import datetime

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from aap_eda.core import models

DELETE_BATCH_SIZE = 1000


class LogPurgeError(Exception):
    """A purge failure that includes the number of committed deletions."""

    def __init__(self, message: str, deleted_count: int):
        self.deleted_count = deleted_count
        super().__init__(message)


def delete_logs_older_than(cutoff: datetime) -> int:
    """Delete old logs globally in committed batches up to a fixed ID."""
    cutoff_timestamp = cutoff.timestamp()
    qualifying = models.RulebookProcessLog.objects.filter(
        log_timestamp__lt=cutoff_timestamp
    )
    max_id = qualifying.aggregate(max_id=Max("id"))["max_id"]
    if max_id is None:
        return 0

    deleted_count = 0
    last_id = 0
    model_label = models.RulebookProcessLog._meta.label
    try:
        while last_id < max_id:
            batch_ids = list(
                qualifying.filter(id__gt=last_id, id__lte=max_id)
                .order_by("id")
                .values_list("id", flat=True)[:DELETE_BATCH_SIZE]
            )
            if not batch_ids:
                break
            with transaction.atomic():
                _, deleted_by_model = models.RulebookProcessLog.objects.filter(
                    id__in=batch_ids,
                    log_timestamp__lt=cutoff_timestamp,
                ).delete()
            deleted_count += deleted_by_model.get(model_label, 0)
            last_id = batch_ids[-1]
    except Exception as exc:
        raise LogPurgeError(
            f"Log deletion failed after {deleted_count} committed rows: {exc}",
            deleted_count,
        ) from exc
    return deleted_count


def create_audit_trail(
    cutoff: datetime,
    *,
    activation_ids: list[int] | None = None,
    activation_names: list[str] | None = None,
) -> int:
    """Create opt-in audit logs for all or selected activation processes."""
    instances = models.RulebookProcess.objects.all()
    if activation_ids or activation_names:
        instances = instances.filter(
            Q(activation_id__in=activation_ids or [])
            | Q(activation__name__in=activation_names or [])
            | Q(activation__isnull=True)
        )

    max_id = instances.aggregate(max_id=Max("id"))["max_id"]
    if max_id is None:
        return 0

    now = timezone.now()
    cutoff_text = cutoff.strftime("%Y-%m-%d %H:%M:%S UTC")
    audit_text = (
        f"All log records older than {cutoff_text} were purged at "
        f"{now.strftime('%Y-%m-%d %H:%M:%S UTC')}."
    )
    created = 0
    last_id = 0
    while last_id < max_id:
        ids = list(
            instances.filter(id__gt=last_id, id__lte=max_id)
            .order_by("id")
            .values_list("id", flat=True)[:DELETE_BATCH_SIZE]
        )
        if not ids:
            break
        try:
            with transaction.atomic():
                batch = [
                    models.RulebookProcessLog(
                        log=audit_text,
                        activation_instance_id=instance_id,
                        log_timestamp=int(now.timestamp()),
                    )
                    for instance_id in ids
                ]
                models.RulebookProcessLog.objects.bulk_create(batch)
            created += len(batch)
            last_id = ids[-1]
        except Exception as exc:
            raise LogPurgeError(
                f"Audit trail creation failed after deleting logs; "
                f"{created} audit rows were committed: {exc}",
                0,
            ) from exc
    return created
