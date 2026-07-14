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
from datetime import timedelta

from ansible_base.lib.utils.db import advisory_lock
from django.conf import settings
from django.utils import timezone

from aap_eda.core.utils.delete_log_util import delete_logs_older_than

LOGGER = logging.getLogger(__name__)


def purge_old_log_records() -> None:
    """Purge log records older than the configured retention period.

    Ensures only one task is executed at a time.
    """
    with advisory_lock("purge_old_log_records", wait=False) as acquired:
        if not acquired:
            LOGGER.debug(
                "purge_old_log_records already running, exiting",
            )
            return

        _purge_old_log_records()


def _purge_old_log_records() -> None:
    retention_days = settings.LOG_RETENTION_DAYS
    if retention_days <= 0:
        return

    cutoff = timezone.now() - timedelta(days=retention_days)
    deleted = delete_logs_older_than(cutoff)

    if deleted:
        LOGGER.info(
            "Purged %d log records older than %d days",
            deleted,
            retention_days,
        )
