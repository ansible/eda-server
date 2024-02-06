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

from django.conf import settings

import aap_eda.tasks.activation_request_queue as requests_queue
from aap_eda.core import models
from aap_eda.core.enums import ActivationRequest, ActivationStatus
from aap_eda.core.models import ActivationRequestQueue
from aap_eda.core.tasking import unique_enqueue
from aap_eda.services.activation.manager import ActivationManager

from .job_control import JobControl

LOGGER = logging.getLogger(__name__)


def _manage_activation_job_id(activation_id: int) -> str:
    """Return the unique job id for the activation manager task."""
    return f"activation-{activation_id}"


def _manage(activation_id: int) -> None:
    """Manage the activation with the given id.

    It will run pending user requests or monitor the activation
    if there are no pending requests.
    """
    try:
        activation = models.Activation.objects.get(id=activation_id)
    except models.Activation.DoesNotExist:
        LOGGER.warning(
            f"Activation {activation_id} no longer exists, "
            "activation manager task will not be processed",
        )
        return

    has_request_processed = False
    while_condition = True
    while while_condition:
        pending_requests = requests_queue.peek_all(activation_id)
        while_condition = bool(pending_requests)
        for request in pending_requests:
            if _run_request(activation, request):
                requests_queue.pop_until(activation_id, request.id)
                has_request_processed = True
            else:
                while_condition = False
                break

    if (
        not has_request_processed
        and activation.status == ActivationStatus.RUNNING
    ):
        LOGGER.info(
            f"Processing monitor request for activation {activation_id}",
        )
        ActivationManager(activation).monitor()


def _run_request(
    activation: models.Activation,
    request: ActivationRequestQueue,
) -> bool:
    """Attempt to run a request for an activation via the manager."""
    LOGGER.info(
        f"Processing request {request.request} for activation "
        f"{activation.id}",
    )
    start_commands = [ActivationRequest.START, ActivationRequest.AUTO_START]
    if request.request in start_commands and not _can_start_new_activation(
        activation,
    ):
        return False

    manager = ActivationManager(activation)
    try:
        if request.request in start_commands:
            manager.start(
                is_restart=request.request == ActivationRequest.AUTO_START,
            )
        elif request.request == ActivationRequest.STOP:
            manager.stop()
        elif request.request == ActivationRequest.RESTART:
            manager.restart()
        elif request.request == ActivationRequest.DELETE:
            manager.delete()
    except Exception as e:
        LOGGER.exception(
            f"Failed to process request {request.request} for "
            f"activation {activation.id}. Reason {str(e)}",
        )
    return True


def _can_start_new_activation(activation: models.Activation) -> bool:
    num_running_activations = models.Activation.objects.filter(
        status__in=[ActivationStatus.RUNNING, ActivationStatus.STARTING],
    ).count()
    if num_running_activations >= settings.MAX_RUNNING_ACTIVATIONS:
        LOGGER.info(
            "No capacity to start a new activation. "
            f"Activation {activation.id} is postponed",
        )
        return False
    return True


def delete_job(control: JobControl) -> None:
    """Create a request to delete the specified job."""
    control.make_delete_request()
    unique_enqueue(control.queue_name(), control.job_id, _manage, control.id)


def restart_job(control: JobControl) -> None:
    """Create a request to restart the specified job."""
    control.make_restart_request()
    unique_enqueue(control.queue_name(), control.job_id, _manage, control.id)


def start_job(control: JobControl) -> None:
    """Create a request to start the specified job."""
    control.make_start_request()
    unique_enqueue(control.queue_name(), control.job_id, _manage, control.id)


def stop_job(control: JobControl) -> None:
    """Create a request to stop the specified job."""
    control.make_stop_request()
    unique_enqueue(control.queue_name(), control.job_id, _manage, control.id)


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
