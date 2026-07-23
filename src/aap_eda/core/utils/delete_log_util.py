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

from datetime import datetime

from django.db.models import Q
from django.utils import timezone

from aap_eda.core import models


def delete_logs_older_than(cutoff: datetime) -> int:
    """Delete all RulebookProcessLog records older than the cutoff.

    Returns the number of records deleted.
    """
    cutoff_ts = int(cutoff.timestamp())
    deleted, _ = models.RulebookProcessLog.objects.filter(
        log_timestamp__lt=cutoff_ts,
    ).delete()
    return deleted


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
