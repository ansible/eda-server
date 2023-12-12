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
from aap_eda.core.tasking import enqueue_delay

LOGGER = logging.getLogger(__name__)


def system_restart_activation(activation_id: int, delay_seconds: int) -> None:
    """Create a request from the system to start the activation.

    This function is intended to be used by the manager to schedule
    a start of the activation for restart policies.
    """
    LOGGER.debug(
        f"Queuing auto-start for activation {activation_id} "
        f"in {delay_seconds} seconds",
    )
    enqueue_delay("default", delay_seconds, _queue_auto_start, activation_id)


def _queue_auto_start(activation_id: int) -> None:
    LOGGER.info(f"Requesting auto-start for activation {activation_id}")
    try:
        requests_queue.push(activation_id, ActivationRequest.AUTO_START)
    except IntegrityError:
        LOGGER.warning(
            f"Activation {activation_id} no longer exists, "
            "auto-start request will not be processed",
        )
