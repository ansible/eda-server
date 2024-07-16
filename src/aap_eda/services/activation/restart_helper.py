#  Copyright 2023 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0pass
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import logging

from django.db.utils import IntegrityError

import aap_eda.tasks.activation_request_queue as requests_queue
from aap_eda.core.enums import ActivationRequest
from aap_eda.core.tasking import enqueue_delay, queue_cancel_job

LOGGER = logging.getLogger(__name__)


def auto_start_job_id(process_parent_type: str, id: int) -> str:
    """Generate the auto-start job id for use in enqueuing and cancelling."""
    return f"auto-start-{process_parent_type}-{id}"


def system_cancel_restart_activation(
    process_parent_type: str, id: int
) -> None:
    """Cancel the restart for the activation.

    The restart may not exist.
    """
    LOGGER.debug(f"Cancelling auto-start for {process_parent_type} {id}")
    queue_cancel_job("default", auto_start_job_id(process_parent_type, id))


def system_restart_activation(
    process_parent_type: str, id: int, delay_seconds: int
) -> None:
    """Create a request from the system to start the activation.

    This function is intended to be used by the manager to schedule
    a start of the activation for restart policies.
    """
    LOGGER.debug(
        f"Queuing auto-start for {process_parent_type} {id} "
        f"in {delay_seconds} seconds",
    )
    enqueue_delay(
        "default",
        auto_start_job_id(process_parent_type, id),
        delay_seconds,
        _queue_auto_start,
        process_parent_type,
        id,
    )


def _queue_auto_start(process_parent_type: str, id: int) -> None:
    LOGGER.info(f"Requesting auto-start for {process_parent_type} {id}")
    try:
        requests_queue.push(
            process_parent_type, id, ActivationRequest.AUTO_START
        )
    except IntegrityError as exc:
        LOGGER.warning(exc)
