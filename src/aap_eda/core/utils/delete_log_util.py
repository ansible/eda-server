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

from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil

from django.db import transaction
from django.db.models import Max

from aap_eda.core import models

PROCESS_PAGE_SIZE = 1000


def _utc_text(value: datetime) -> str:
    """Format datetime as UTC string with optional microseconds."""
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


@dataclass(frozen=True)
class _PurgeOptions:
    """Validated purge operation parameters."""

    cutoff: datetime | None
    cutoff_timestamp: float | None
    selected_ids: set[int] | None
    audit_trail: bool
    internal_job_uuid: str | None
    purge_all_logs: bool


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


def _marker_text(
    cutoff: datetime | None,
    purge_time: datetime,
    count: int,
    tracking_id: str | None,
    orphaned: bool,
    internal_job_uuid: str | None,
) -> str:
    """Format audit marker text with purge metadata."""
    details = [f"Recorded at: {_utc_text(purge_time)}"]
    noun = "record" if count == 1 else "records"
    if cutoff is None:
        text = f"Purged {count} log {noun} globally."
    else:
        text = f"Purged {count} log {noun} older than {_utc_text(cutoff)}."
    if internal_job_uuid is not None:
        details.append(f"Purge Job ID: {internal_job_uuid}")
    if tracking_id and tracking_id.strip():
        details.append(f"Activation Lifecycle ID: {tracking_id.strip()}")
    elif orphaned:
        details.append(
            "Activation Lifecycle ID: unavailable (orphaned process)"
        )
    return f"{text} [{' | '.join(details)}]"


def _validate_purge_options(
    cutoff: datetime | None,
    *,
    activation_ids: list[int] | None,
    activation_names: list[str] | None,
    audit_trail: bool,
    internal_job_uuid: str | None,
    purge_all_logs: bool,
) -> _PurgeOptions:
    """Validate purge parameters and return configuration object."""
    if not isinstance(purge_all_logs, bool):
        raise ValueError("purge_all_logs must be a boolean.")
    if purge_all_logs:
        if any(
            selector is not None
            for selector in (activation_ids, activation_names)
        ):
            raise ValueError(
                "--purge-all-logs cannot be combined with "
                "activation selectors."
            )
        if not audit_trail:
            raise ValueError("--purge-all-logs requires audit trail.")
        selected_ids = None
        cutoff_timestamp = cutoff.timestamp() if cutoff is not None else None
    else:
        if cutoff is None:
            raise ValueError("A cutoff is required unless purging all logs.")
        selected_ids = resolve_activation_ids(activation_ids, activation_names)
        cutoff_timestamp = cutoff.timestamp()
    return _PurgeOptions(
        cutoff,
        cutoff_timestamp,
        selected_ids,
        audit_trail,
        internal_job_uuid,
        purge_all_logs,
    )


def _write_audit_marker(
    process_id: int,
    activation_id: int | None,
    tracking_id: str | None,
    deleted_count: int,
    options: _PurgeOptions,
) -> int:
    """Create audit marker log record for a purge operation."""
    purge_time = datetime.now(timezone.utc)
    marker_timestamp = max(
        ceil(purge_time.timestamp()),
        ceil(options.cutoff_timestamp)
        if options.cutoff_timestamp is not None
        else 0,
    )
    marker_text = _marker_text(
        options.cutoff,
        purge_time,
        deleted_count,
        tracking_id,
        activation_id is None,
        options.internal_job_uuid,
    )
    marker = models.RulebookProcessLog.objects.create(
        activation_instance_id=process_id,
        log=marker_text,
        log_timestamp=marker_timestamp,
        log_created_at=purge_time,
    )
    return marker.id


def _purge_process_logs(process: tuple, options: _PurgeOptions) -> int:
    """Delete logs for one process matching purge criteria."""
    process_id, activation_id, tracking_id = process
    logs = models.RulebookProcessLog.objects.filter(
        activation_instance_id=process_id
    )
    if options.cutoff_timestamp is not None:
        logs = logs.filter(log_timestamp__lt=options.cutoff_timestamp)
    if options.selected_ids is not None:
        logs = logs.filter(
            activation_instance__activation_id__in=options.selected_ids
        )
    with transaction.atomic():
        deleted_count, _ = logs.delete()
        if options.audit_trail and deleted_count:
            _write_audit_marker(
                process_id,
                activation_id,
                tracking_id,
                deleted_count,
                options,
            )
    return deleted_count


def purge_unattached_logs(cutoff_timestamp: float | None = None) -> int:
    """Delete logs not linked to any activation instance."""
    logs = models.RulebookProcessLog.objects.filter(
        activation_instance_id__isnull=True
    )
    if cutoff_timestamp is not None:
        logs = logs.filter(log_timestamp__lt=cutoff_timestamp)
    deleted_count, _ = logs.delete()
    return deleted_count


def delete_logs_older_than(
    cutoff: datetime | None,
    *,
    activation_ids: list[int] | None = None,
    activation_names: list[str] | None = None,
    audit_trail: bool = True,
    internal_job_uuid: str | None = None,
    purge_all_logs: bool = False,
) -> int:
    """Purge qualifying logs one process at a time."""
    options = _validate_purge_options(
        cutoff,
        activation_ids=activation_ids,
        activation_names=activation_names,
        audit_trail=audit_trail,
        internal_job_uuid=internal_job_uuid,
        purge_all_logs=purge_all_logs,
    )
    processes = models.RulebookProcess.objects.all()
    if options.selected_ids is not None:
        processes = processes.filter(activation_id__in=options.selected_ids)
    highest_process_id = processes.aggregate(max_id=Max("id"))["max_id"]
    if highest_process_id is None:
        return 0

    deleted_count = 0
    last_process_id = 0
    try:
        while last_process_id < highest_process_id:
            process_batch = list(
                processes.filter(
                    id__gt=last_process_id, id__lte=highest_process_id
                )
                .order_by("id")
                .values_list(
                    "id", "activation_id", "activation__log_tracking_id"
                )[:PROCESS_PAGE_SIZE]
            )
            if not process_batch:
                break
            for process in process_batch:
                deleted_count += _purge_process_logs(process, options)
            last_process_id = process_batch[-1][0]
    except Exception as exc:
        raise LogPurgeError(
            f"Log purge failed after {deleted_count} committed rows: {exc}",
            deleted_count,
        ) from exc
    return deleted_count
