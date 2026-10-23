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

import logging
import re
from uuid import uuid4

from ansible_base.lib.utils.db import advisory_lock
from dispatcherd.publish import submit_task
from django.conf import settings
from django.core.management import call_command

from aap_eda import utils
from aap_eda.core.utils.delete_log_util import LogPurgeError

logger = logging.getLogger(__name__)

MANAGEMENT_TASKS_QUEUE = "default"
LOG_PURGE_TASK_TIMEOUT_SECONDS = 3600
_DELETED_COUNT = re.compile(r"^Purged (\d+) log records")


def submit_log_purge(
    *,
    before_date: str | None = None,
    retention_duration: str | None = None,
    audit_trail: bool = True,
    activation_ids: list[int] | None = None,
    activation_names: list[str] | None = None,
) -> str:
    """Submit a fixed-purpose log purge task."""
    command_options = {"audit_trail": audit_trail}
    if before_date is not None:
        command_options["date"] = before_date
    if retention_duration is not None:
        command_options["retention_duration"] = retention_duration
    if activation_ids is not None:
        command_options["activation-ids"] = activation_ids
    if activation_names is not None:
        command_options["activation-names"] = activation_names

    return aap_eda_manage_commands(
        "purge_log_records",
        timeout=LOG_PURGE_TASK_TIMEOUT_SECONDS,
        **command_options,
    )


def aap_eda_manage_commands(
    command: str, *, timeout: int | None = None, **command_options
) -> str:
    """Submit a Django management command to the default worker queue.

    The API uses ``submit_log_purge`` so its request cannot choose a command.
    This generic entry point remains available to internal callers.
    """
    job_id = str(uuid4())
    if command == "purge_log_records":
        command_options["internal-job-uuid"] = job_id
    job_data, _ = submit_task(
        _aap_eda_manage,
        args=(job_id, command, command_options),
        queue=utils.sanitize_postgres_identifier(MANAGEMENT_TASKS_QUEUE),
        timeout=(
            settings.DISPATCHERD_PROJECT_TASK_TIMEOUT
            if timeout is None
            else timeout
        ),
        uuid=job_id,
    )
    return str(job_data["uuid"])


def _aap_eda_manage(job_id: str, command: str, command_options: dict) -> dict:
    """Run a management command under an advisory lock."""
    logger.info(
        "Management command started job_id=%s command=%s", job_id, command
    )
    with advisory_lock(command, wait=False) as acquired:
        if not acquired:
            reason = f"another task holds the advisory lock for {command}"
            logger.warning(
                "Management command skipped job_id=%s command=%s "
                "status=skipped reason=%s",
                job_id,
                command,
                reason,
            )
            return {
                "job_id": job_id,
                "command": command,
                "status": "skipped",
                "reason": reason,
            }

        try:
            command_output = call_command(
                command, no_color=True, **command_options
            )
        except Exception as exc:
            cause = exc.__cause__
            if command == "purge_log_records" and isinstance(
                cause, LogPurgeError
            ):
                logger.exception(
                    "Management command failed job_id=%s command=%s "
                    "status=failed deleted_count=%d",
                    job_id,
                    command,
                    cause.deleted_count,
                )
            else:
                logger.exception(
                    "Management command failed job_id=%s command=%s "
                    "status=failed",
                    job_id,
                    command,
                )
            raise

        result = {
            "job_id": job_id,
            "command": command,
            "status": "completed",
        }
        if command == "purge_log_records":
            match = _DELETED_COUNT.match(command_output or "")
            deleted_count = int(match.group(1)) if match else 0
            result["deleted"] = deleted_count
            result["status"] = "completed" if deleted_count else "no-op"
            logger.info(
                "Log purge finished job_id=%s status=%s deleted_count=%d",
                job_id,
                result["status"],
                deleted_count,
            )
        else:
            logger.info(
                "Management command finished job_id=%s command=%s "
                "status=completed",
                job_id,
                command,
            )
        return result
