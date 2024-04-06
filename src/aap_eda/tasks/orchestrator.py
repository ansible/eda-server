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
from typing import Union

from django.core.exceptions import ObjectDoesNotExist

import aap_eda.tasks.activation_request_queue as requests_queue
from aap_eda.core import models
from aap_eda.core.enums import (
    ActivationRequest,
    ActivationStatus,
    ProcessParentType,
)
from aap_eda.core.models import Activation, ActivationRequestQueue, EventStream
from aap_eda.core.tasking import unique_enqueue
from aap_eda.services.activation import exceptions
from aap_eda.services.activation.manager import ActivationManager

LOGGER = logging.getLogger(__name__)


def _manage_process_job_id(process_parent_type: str, id: int) -> str:
    """Return the unique job id for the activation manager task."""
    return f"{process_parent_type}-{id}"


def _manage(process_parent_type: str, id: int) -> None:
    """Manage the activation with the given id.

    It will run pending user requests or monitor the activation
    if there are no pending requests.
    """
    try:
        if process_parent_type == ProcessParentType.ACTIVATION:
            klass = Activation
        else:
            klass = EventStream
        process_parent = klass.objects.get(id=id)
    except ObjectDoesNotExist:
        LOGGER.warning(
            f"{process_parent_type} with {id} no longer exists, "
            "activation manager task will not be processed",
        )
        return

    has_request_processed = False
    while_condition = True
    while while_condition:
        pending_requests = requests_queue.peek_all(process_parent_type, id)
        while_condition = bool(pending_requests)
        for request in pending_requests:
            if _run_request(process_parent, request):
                requests_queue.pop_until(process_parent_type, id, request.id)
                has_request_processed = True
            else:
                while_condition = False
                break

    if (
        not has_request_processed
        and process_parent.status == ActivationStatus.RUNNING
    ):
        LOGGER.info(
            f"Processing monitor request for {process_parent_type} {id}",
        )
        ActivationManager(process_parent).monitor()


def _run_request(
    process_parent: Union[Activation, EventStream],
    request: ActivationRequestQueue,
) -> bool:
    """Attempt to run a request for an activation via the manager."""
    process_parent_type = type(process_parent).__name__
    LOGGER.info(
        f"Processing request {request.request} for {process_parent_type} "
        f"{process_parent.id}",
    )
    start_commands = [ActivationRequest.START, ActivationRequest.AUTO_START]
    if (
        request.request in start_commands
        and not ActivationManager.check_new_process_allowed(
            process_parent_type,
            process_parent.id,
        )
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
    except exceptions.MaxRunningProcessesError:
        return False
    except Exception as e:
        LOGGER.exception(
            f"Failed to process request {request.request} for "
            f"{process_parent_type} {process_parent.id}. Reason {str(e)}",
        )
    return True


def _enqueue_process(
    job_id: str,
    process_parent_type: ProcessParentType,
    parent_id: int,
    *args,
    **kwargs,
) -> None:
    match process_parent_type:
        case ProcessParentType.ACTIVATION:
            klass = Activation
        case ProcessParentType.EVENT_STREAM:
            klass = EventStream
        case _:
            raise ValueError(
                f"unknown process type '{process_parent_type}' specified"
            )
    try:
        process_parent = klass.objects.get(id=parent_id)
    except ObjectDoesNotExist:
        LOGGER.warning(
            f"{process_parent_type} with {parent_id} no longer exists, "
            "job will not be enqueued",
        )
        return

    unique_enqueue(
        "activation",
        job_id,
        _manage,
        process_parent_type,
        parent_id,
        *args,
        result_ttl=process_parent.effective_retention_success_period,
        failure_ttl=process_parent.effective_retention_failure_period,
        **kwargs,
    )


def _make_user_request(
    process_parent_type: ProcessParentType,
    id: int,
    request_type: ActivationRequest,
) -> None:
    """Enqueue a task to manage the activation with the given id."""
    requests_queue.push(process_parent_type, id, request_type)
    job_id = _manage_process_job_id(process_parent_type, id)
    _enqueue_process(job_id, process_parent_type, id)


def start_rulebook_process(
    process_parent_type: ProcessParentType, id: int
) -> None:
    """Create a request to start the activation with the given id."""
    _make_user_request(process_parent_type, id, ActivationRequest.START)


def stop_rulebook_process(
    process_parent_type: ProcessParentType, id: int
) -> None:
    """Create a request to stop the activation with the given id."""
    _make_user_request(process_parent_type, id, ActivationRequest.STOP)


def delete_rulebook_process(
    process_parent_type: ProcessParentType, id: int
) -> None:
    """Create a request to delete the activation with the given id."""
    _make_user_request(process_parent_type, id, ActivationRequest.DELETE)


def restart_rulebook_process(
    process_parent_type: ProcessParentType, id: int
) -> None:
    """Create a request to restart the activation with the given id."""
    _make_user_request(process_parent_type, id, ActivationRequest.RESTART)


def monitor_rulebook_processes() -> None:
    """Monitor activations scheduled task.

    Started by the scheduler, executed by the default worker.
    It enqueues a task for each activation that needs to be managed.
    Handles both user requests and monitoring of running activations.
    It will not enqueue a task if there is already one for the same
    activation.
    """
    # run pending user requests
    for process_parent_type, id in requests_queue.list_requests():
        job_id = _manage_process_job_id(process_parent_type, id)
        _enqueue_process(job_id, process_parent_type, id)

    # monitor running instances
    for process in models.RulebookProcess.objects.filter(
        status=ActivationStatus.RUNNING,
    ):
        process_parent_type = str(process.parent_type)
        if process_parent_type == ProcessParentType.ACTIVATION:
            id = process.activation_id
        else:
            id = process.event_stream_id
        job_id = _manage_process_job_id(process_parent_type, id)
        _enqueue_process(job_id, process_parent_type, id)
