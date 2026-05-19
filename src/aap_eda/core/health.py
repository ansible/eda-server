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
from typing import Optional

from django.conf import settings

from aap_eda.api import exceptions as api_exc
from aap_eda.tasks.orchestrator import check_rulebook_queue_health
from aap_eda.tasks.project import check_default_worker_health

logger = logging.getLogger(__name__)


def check_activation_worker_health(
    queue_name: Optional[str] = None,
) -> bool:
    """Check activation worker health (rulebook queues only).

    Args:
        queue_name: If provided, check only this specific queue.
                    If None, check all configured queues and return
                    True if any is healthy.

    Returns:
        bool: True if activation workers are healthy, False otherwise.
    """
    try:
        if queue_name is not None:
            return check_rulebook_queue_health(queue_name)

        rulebook_queues = getattr(settings, "RULEBOOK_WORKER_QUEUES", [])
        if rulebook_queues:
            return any(check_rulebook_queue_health(q) for q in rulebook_queues)

        # If no rulebook queues configured, activation workers are considered
        # healthy
        return True
    except Exception as e:
        logger.error(
            f"Health check failed for activation workers: {e}",
            exc_info=True,
        )
        return False


def check_dispatcherd_workers_health(
    raise_exceptions=False,
    queue_name: Optional[str] = None,
) -> bool:
    """Check dispatcherd worker health for both default and activation workers.

    Args:
        raise_exceptions: If True, raises WorkerUnavailable with
                         specific worker_type. If False, returns boolean.
        queue_name: If provided, check only this specific activation queue.
                    If None, check all configured queues (healthy if any
                    is up).

    Returns:
        bool: True if both worker types are healthy, False otherwise.
              Only relevant when raise_exceptions=False.

    Raises:
        WorkerUnavailable: When raise_exceptions=True and a worker
                          type is unhealthy, with specific worker_type.
    """
    try:
        # Check default workers first
        if not check_default_worker_health():
            if raise_exceptions:
                raise api_exc.WorkerUnavailable(worker_type="default")
            return False

        # Check activation workers
        if not check_activation_worker_health(queue_name=queue_name):
            if raise_exceptions:
                raise api_exc.WorkerUnavailable(worker_type="activation")
            return False

        # If we get here, both worker types are healthy
        return True

    except Exception as e:
        if not raise_exceptions:
            logger.error(
                f"Health check failed for dispatcherd workers: {e}",
                exc_info=True,
            )
            return False
        else:
            # Re-raise WorkerUnavailable exceptions when in exception mode
            if (
                hasattr(e, "default_code")
                and e.default_code == "worker_unavailable"
            ):
                raise
            # For other exceptions, log and raise a generic WorkerUnavailable
            logger.error(
                f"Health check failed for dispatcherd workers: {e}",
                exc_info=True,
            )
            raise api_exc.WorkerUnavailable()
