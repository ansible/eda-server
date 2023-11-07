#  Copyright 2023 Red Hat, Inc.
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

import aap_eda.tasks.activation_request_queue as requests_queue
from aap_eda.core import models
from aap_eda.core.enums import ActivationRequest, ActivationStatus
from aap_eda.core.tasking import unique_enqueue
from aap_eda.services.activation.manager import ActivationManager

LOGGER = logging.getLogger(__name__)


def _manage_activation_job_id(activation_id: int) -> str:
    """Return the unique job id for the activation manager task."""
    return f"activation-{activation_id}"


def _manage(activation_id: int) -> None:
    """Manage the activation with the given id.

    It will run pending user requests or monitor the activation
    if there are no pending requests.
    """
    activation = models.Activation.objects.get(id=activation_id)
    has_user_requests = False
    pending_requests = requests_queue.peek_all(activation_id)
    while pending_requests:
        for request in pending_requests:
            LOGGER.info(
                f"Processing request {request.request} for activation "
                f"{activation_id}",
            )
            manager = ActivationManager(activation)
            try:
                if request.request == ActivationRequest.START:
                    manager.start()
                elif request.request == ActivationRequest.STOP:
                    manager.stop()
                elif request.request == ActivationRequest.RESTART:
                    manager.restart()
                elif request.request == ActivationRequest.DELETE:
                    manager.delete()
            except Exception:
                LOGGER.exception(
                    f"Failed to process request {request.request} for "
                    f"activation {activation_id}",
                )
                raise
            finally:
                requests_queue.pop_until(activation_id, request.id)
        has_user_requests = True
        pending_requests = requests_queue.peek_all(activation_id)

    if not has_user_requests:
        LOGGER.info(
            f"Processing monitor request for activation {activation_id}",
        )
        ActivationManager(activation).monitor()


def _make_user_request(
    activation_id: int,
    request_type: ActivationRequest,
) -> None:
    """Enqueue a task to manage the activation with the given id."""
    requests_queue.push(activation_id, request_type)
    job_id = _manage_activation_job_id(activation_id)
    unique_enqueue("activation", job_id, _manage, activation_id)


def start_activation(activation_id: int) -> None:
    """Create a request to start the activation with the given id."""
    _make_user_request(activation_id, ActivationRequest.START)


def stop_activation(activation_id: int) -> None:
    """Create a request to stop the activation with the given id."""
    _make_user_request(activation_id, ActivationRequest.STOP)


def delete_activation(activation_id: int) -> None:
    """Create a request to delete the activation with the given id."""
    _make_user_request(activation_id, ActivationRequest.DELETE)


def restart_activation(activation_id: int) -> None:
    """Create a request to restart the activation with the given id."""
    _make_user_request(activation_id, ActivationRequest.RESTART)


def monitor_activations() -> None:
    """Monitor activations scheduled task.

    Started by the scheduler, executed by the default worker.
    It enqueues a task for each activation that needs to be managed.
    Handles both user requests and monitoring of running activations.
    It will not enqueue a task if there is already one for the same
    activation.
    """
    # run pending user requests
    for activation_id in requests_queue.list_activations():
        job_id = _manage_activation_job_id(activation_id)
        unique_enqueue("activation", job_id, _manage, activation_id)

    # monitor running instances
    for activation in models.Activation.objects.filter(
        status=ActivationStatus.RUNNING,
    ):
        job_id = _manage_activation_job_id(activation.id)
        unique_enqueue("activation", job_id, _manage, activation.id)
