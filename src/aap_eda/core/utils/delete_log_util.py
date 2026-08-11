#  Copyright 2025 Red Hat, Inc.
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

import logging
from datetime import datetime

from django.db.models import Q
from django.utils import timezone

from aap_eda.core import models

logger = logging.getLogger(__name__)

BATCH_SIZE = 10_000


def delete_logs_older_than(
    cutoff: datetime,
    activation_id: int | None = None,
) -> int:
    """Delete all RulebookProcessLog records older than the cutoff.

    If activation_id is provided, only delete logs for instances
    belonging to that activation.

    Returns the number of records deleted.
    """
    cutoff_ts = int(cutoff.timestamp())
    qs = models.RulebookProcessLog.objects.filter(
        log_timestamp__lt=cutoff_ts,
    )
    if activation_id is not None:
        instance_ids = models.RulebookProcess.objects.filter(
            activation_id=activation_id,
        ).values_list("id", flat=True)
        qs = qs.filter(activation_instance_id__in=instance_ids)
    return _batched_delete(qs)


def delete_logs_for_activation(activation_id: int) -> int:
    """Delete all logs for a given activation's instances.

    Returns the number of records deleted.
    """
    instance_ids = models.RulebookProcess.objects.filter(
        activation_id=activation_id,
    ).values_list("id", flat=True)
    qs = models.RulebookProcessLog.objects.filter(
        activation_instance_id__in=instance_ids,
    )
    return _batched_delete(qs)


def delete_all_logs(cutoff: datetime | None = None) -> int:
    """Delete all RulebookProcessLog records.

    If cutoff is provided, only delete logs older than the cutoff.

    Returns the number of records deleted.
    """
    qs = models.RulebookProcessLog.objects.all()
    if cutoff is not None:
        cutoff_ts = int(cutoff.timestamp())
        qs = qs.filter(log_timestamp__lt=cutoff_ts)
    return _batched_delete(qs)


def _batched_delete(queryset) -> int:
    """Delete queryset in batches to avoid long-running queries."""
    total_deleted = 0
    upper_id = queryset.order_by("-id").values_list("id", flat=True).first()
    if upper_id is None:
        return total_deleted
    queryset = queryset.filter(id__lte=upper_id)

    while True:
        batch_ids = list(queryset.values_list("id", flat=True)[:BATCH_SIZE])
        if not batch_ids:
            break
        deleted, _ = models.RulebookProcessLog.objects.filter(
            id__in=batch_ids,
        ).delete()
        total_deleted += deleted
        logger.info("Purged %d log records (batch)", deleted)
    return total_deleted


def create_audit_trail(
    cutoff: datetime,
    activation_ids: list[int] | None = None,
    activation_names: list[str] | None = None,
) -> int:
    """Create audit trail log entries recording a purge operation.

    If activation_ids or activation_names are provided, audit entries
    are scoped to those activations plus orphaned records. Otherwise,
    audit entries are created for all RulebookProcess instances.

    Returns the number of audit entries created.
    """
    ids = activation_ids or []
    names = activation_names or []

    if not ids and not names:
        instances = models.RulebookProcess.objects.all()
    else:
        instances = models.RulebookProcess.objects.filter(
            Q(activation__id__in=ids)
            | Q(activation__name__in=names)
            | Q(activation__isnull=True),
        )

    now = timezone.now()
    dt = now.strftime("%Y-%m-%d %H:%M:%S")
    now_ts = int(now.timestamp())

    audit_logs = [
        models.RulebookProcessLog(
            log=(
                f"All log records older than "
                f"{cutoff.strftime('%Y-%m-%d')} "
                f"were purged at {dt}."
            ),
            activation_instance_id=instance.id,
            log_timestamp=now_ts,
        )
        for instance in instances
    ]

    if audit_logs:
        models.RulebookProcessLog.objects.bulk_create(audit_logs)

    return len(audit_logs)
