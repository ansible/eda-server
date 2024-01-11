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
import typing as tp

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

import aap_eda.tasks.activation_request_queue as requests_queue
from aap_eda.core.enums import ActivationRequest, ActivationStatus
from aap_eda.core.models import ActivationRequestQueue
from aap_eda.core.models.proxies import ProcessParentProxy
from aap_eda.core.tasking import unique_enqueue
from aap_eda.services.activation.manager import ActivationManager

LOGGER = logging.getLogger(__name__)


def _manage_activation_job_id(process_parent: ProcessParentProxy) -> str:
    """Return the unique job id for the process parent manager task."""
    if process_parent.is_activation:
        return f"activation-{process_parent.id}"
    return f"source-{process_parent.id}"


def _manage(process_parent_data: dict[str, tp.Any]) -> None:
    """Manage the activation with the given id.

    It will run pending user requests or monitor the activation
    if there are no pending requests.
    """
    try:
        process_parent = ProcessParentProxy.from_dict(process_parent_data)
    except ObjectDoesNotExist:
        LOGGER.warning(
            f"Process parent {process_parent_data['id']} no longer exists, "
            "activation manager task will not be processed",
        )
        return

    has_request_processed = False
    while_condition = True
    while while_condition:
        pending_requests = requests_queue.peek_all(process_parent)
        while_condition = bool(pending_requests)
        for request in pending_requests:
            if _run_request(process_parent, request):
                requests_queue.pop_until(process_parent, request.id)
                has_request_processed = True
            else:
                while_condition = False
                break

    if (
        not has_request_processed
        and process_parent.status == ActivationStatus.RUNNING
    ):
        LOGGER.info(
            f"Processing monitor request for parent {process_parent.id}",
        )
        ActivationManager(process_parent).monitor()


def _run_request(
    process_parent: ProcessParentProxy,
    request: ActivationRequestQueue,
) -> bool:
    """Attempt to run a request for an activation via the manager."""
    LOGGER.info(
        f"Processing request {request.request} for activation "
        f"{process_parent.id}",
    )
    start_commands = [
        ActivationRequest.START,
        ActivationRequest.AUTO_START,
    ]
    if request.request in start_commands and not _can_start_new_activation(
        process_parent,
    ):
        return False

    manager = ActivationManager(process_parent)
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
            f"activation {process_parent.id}. Reason {str(e)}",
        )
    return True


def _can_start_new_activation(process_parent: ProcessParentProxy) -> bool:
    num_running_activations = ProcessParentProxy.filter(
        status__in=[ActivationStatus.RUNNING, ActivationStatus.STARTING],
    ).count()
    if num_running_activations >= settings.MAX_RUNNING_ACTIVATIONS:
        LOGGER.info(
            "No capacity to start a new activation. "
            f"Activation {process_parent.id} is postponed",
        )
        return False
    return True


def _make_user_request(
    process_parent: ProcessParentProxy,
    request_type: ActivationRequest,
) -> None:
    """Enqueue a task to manage the process parent with the given id."""
    requests_queue.push(process_parent, request_type)
    job_id = _manage_activation_job_id(process_parent)
    unique_enqueue(
        "activation",
        job_id,
        _manage,
        process_parent_data=process_parent.to_dict(),
    )


def start_activation(process_parent: ProcessParentProxy) -> None:
    """Create a request to start the process parent."""
    _make_user_request(process_parent, ActivationRequest.START)


def stop_activation(process_parent: ProcessParentProxy) -> None:
    """Create a request to stop the process parent."""
    _make_user_request(process_parent, ActivationRequest.STOP)


def delete_activation(process_parent: ProcessParentProxy) -> None:
    """Create a request to delete the process parent."""
    _make_user_request(process_parent, ActivationRequest.DELETE)


def restart_activation(process_parent: ProcessParentProxy) -> None:
    """Create a request to restart the process parent."""
    _make_user_request(process_parent, ActivationRequest.RESTART)


def monitor_activations() -> None:
    """Monitor activations scheduled task.

    Started by the scheduler, executed by the default worker.
    It enqueues a task for each activation that needs to be managed.
    Handles both user requests and monitoring of running activations.
    It will not enqueue a task if there is already one for the same
    activation.
    """
    # run pending user requests
    for process_parent in requests_queue.list_activations():
        job_id = _manage_activation_job_id(process_parent)
        unique_enqueue(
            "activation",
            job_id,
            _manage,
            process_parent_data=process_parent.to_dict(),
        )

    # monitor running instances
    for instance in ProcessParentProxy.filter(
        status=ActivationStatus.RUNNING,
    ):
        process_parent = ProcessParentProxy(instance)
        job_id = _manage_activation_job_id(process_parent)
        unique_enqueue(
            "activation",
            job_id,
            _manage,
            process_parent_data=process_parent.to_dict(),
        )
