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

from datetime import datetime, timezone
from math import ceil

from django.db import transaction
from django.db.models import Max

from aap_eda.core import models

DELETE_BATCH_SIZE = 1000

# This reserved value identifies new markers without a schema change.
PURGE_MARKER_CREATED_AT = datetime(9999, 12, 31, tzinfo=timezone.utc)

# Older versions wrote this fixed message with NULL log_created_at. Text
# matching cannot distinguish an ordinary log with identical content.
LEGACY_MARKER_PATTERN = (
    r"^All log records older than [0-9]{4}-[0-9]{2}-[0-9]{2} "
    r"[0-9]{2}:[0-9]{2}:[0-9]{2} UTC were purged at "
    r"[0-9]{4}-[0-9]{2}-[0-9]{2} "
    r"[0-9]{2}:[0-9]{2}:[0-9]{2} UTC\.$"
)


def _utc_text(value: datetime) -> str:
    value = value.astimezone(timezone.utc)
    time_format = "%Y-%m-%d %H:%M:%S"
    if value.microsecond:
        time_format += ".%f"
    return value.strftime(time_format + " UTC")


class LogPurgeError(Exception):
    """A purge failure that includes the number of committed deletions."""

    def __init__(self, message: str, deleted_count: int):
        self.deleted_count = deleted_count
        super().__init__(message)


def resolve_activation_ids(
    activation_ids: list[int] | None,
    activation_names: list[str] | None,
) -> set[int] | None:
    """Validate every selector and return its union, or None for global."""
    if activation_ids is None and activation_names is None:
        return None
    if activation_ids is not None and (
        not activation_ids
        or any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in activation_ids
        )
    ):
        raise ValueError("Activation IDs must be positive integers.")
    if activation_names is not None and (
        not activation_names
        or any(
            not isinstance(value, str) or not value.strip()
            for value in activation_names
        )
    ):
        raise ValueError("Activation names cannot be blank.")

    requested_ids = set(activation_ids or [])
    requested_names = set(activation_names or [])
    existing_ids = set(
        models.Activation.objects.filter(id__in=requested_ids).values_list(
            "id", flat=True
        )
    )
    if missing := requested_ids - existing_ids:
        raise ValueError(f"Unknown activation IDs: {sorted(missing)}.")

    named_activations = models.Activation.objects.filter(
        name__in=requested_names
    ).values_list("id", "name")
    found_names = set()
    for activation_id, name in named_activations:
        existing_ids.add(activation_id)
        found_names.add(name)
    if missing := requested_names - found_names:
        raise ValueError(f"Unknown activation names: {sorted(missing)}.")
    return existing_ids


def _ordinary_logs(
    process_id: int,
    cutoff_timestamp: float,
    selected_ids: set[int] | None,
):
    logs = models.RulebookProcessLog.objects.filter(
        activation_instance_id=process_id,
        log_timestamp__lt=cutoff_timestamp,
    )
    if selected_ids is not None:
        logs = logs.filter(activation_instance__activation_id__in=selected_ids)
    return logs.exclude(log_created_at=PURGE_MARKER_CREATED_AT).exclude(
        log_created_at__isnull=True,
        log__regex=LEGACY_MARKER_PATTERN,
    )


def _marker_text(
    cutoff: datetime,
    purge_time: datetime,
    count: int,
    tracking_id: str | None,
    orphaned: bool,
    internal_job_uuid: str | None,
) -> str:
    cutoff_text = _utc_text(cutoff)
    purge_text = _utc_text(purge_time)
    text = (
        f"All log records older than {cutoff_text} were purged at "
        f"{purge_text}. Deleted {count} log rows."
    )
    if internal_job_uuid is not None:
        text += f" Job ID: {internal_job_uuid}."
    if tracking_id and tracking_id.strip():
        text += f" Log Tracking id {tracking_id.strip()}."
    elif orphaned:
        text += " Log Tracking id unavailable (orphaned process)."
    return text


def delete_logs_older_than(
    cutoff: datetime,
    *,
    activation_ids: list[int] | None = None,
    activation_names: list[str] | None = None,
    audit_trail: bool = True,
    internal_job_uuid: str | None = None,
) -> int:
    """Purge ordinary logs per process in committed, bounded ID batches."""
    selected_ids = resolve_activation_ids(activation_ids, activation_names)
    cutoff_timestamp = cutoff.timestamp()
    processes = models.RulebookProcess.objects.all()
    if selected_ids is not None:
        processes = processes.filter(activation_id__in=selected_ids)
    highest_process_id = processes.aggregate(max_id=Max("id"))["max_id"]
    if highest_process_id is None:
        return 0

    deleted_count = 0
    last_process_id = 0
    model_label = models.RulebookProcessLog._meta.label
    try:
        while last_process_id < highest_process_id:
            process_batch = list(
                processes.filter(
                    id__gt=last_process_id, id__lte=highest_process_id
                )
                .order_by("id")
                .values_list(
                    "id", "activation_id", "activation__log_tracking_id"
                )[:DELETE_BATCH_SIZE]
            )
            if not process_batch:
                break
            for process_id, activation_id, tracking_id in process_batch:
                qualifying = _ordinary_logs(
                    process_id, cutoff_timestamp, selected_ids
                )
                highest_log_id = qualifying.aggregate(max_id=Max("id"))[
                    "max_id"
                ]
                if highest_log_id is None:
                    continue

                last_log_id = 0
                process_deleted = 0
                marker_id = None
                while last_log_id < highest_log_id:
                    batch_ids = list(
                        qualifying.filter(
                            id__gt=last_log_id, id__lte=highest_log_id
                        )
                        .order_by("id")
                        .values_list("id", flat=True)[:DELETE_BATCH_SIZE]
                    )
                    if not batch_ids:
                        break
                    with transaction.atomic():
                        _, per_model_counts = (
                            _ordinary_logs(
                                process_id, cutoff_timestamp, selected_ids
                            )
                            .filter(id__in=batch_ids)
                            .delete()
                        )
                        batch_deleted = per_model_counts.get(model_label, 0)
                        if audit_trail and batch_deleted:
                            purge_time = datetime.now(timezone.utc)
                            marker_timestamp = max(
                                ceil(purge_time.timestamp()),
                                ceil(cutoff_timestamp),
                            )
                            marker_text = _marker_text(
                                cutoff,
                                purge_time,
                                process_deleted + batch_deleted,
                                tracking_id,
                                activation_id is None,
                                internal_job_uuid,
                            )
                            if marker_id is None:
                                marker = (
                                    models.RulebookProcessLog.objects.create(
                                        activation_instance_id=process_id,
                                        log=marker_text,
                                        log_timestamp=marker_timestamp,
                                        log_created_at=PURGE_MARKER_CREATED_AT,
                                    )
                                )
                                marker_id = marker.id
                            else:
                                updated = (
                                    models.RulebookProcessLog.objects.filter(
                                        pk=marker_id
                                    ).update(
                                        log=marker_text,
                                        log_timestamp=marker_timestamp,
                                    )
                                )
                                if updated != 1:
                                    raise RuntimeError(
                                        "The current purge marker disappeared."
                                    )
                    process_deleted += batch_deleted
                    deleted_count += batch_deleted
                    last_log_id = batch_ids[-1]
            last_process_id = process_batch[-1][0]
    except Exception as exc:
        raise LogPurgeError(
            f"Log purge failed after {deleted_count} committed rows: {exc}",
            deleted_count,
        ) from exc
    return deleted_count
