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
from typing import Optional, Union

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
from aap_eda.services.activation.engine.factory import new_container_engine
from aap_eda.services.activation.manager import ActivationManager

LOGGER = logging.getLogger(__name__)
_MANAGE_TASK = "aap_eda.tasks.orchestrator.manage"


def _manage_process_job_id(process_parent_type: str, id: int) -> str:
    """Return the unique job id for the activation manager task."""
    return f"{process_parent_type}-{id}"


def manage(process_parent_type: str, id: int) -> None:
    """Manage the activation with the given id.

    It will run pending user requests or monitor the activation
    if there are no pending requests.
    """
    process_parent = _get_process_parent(process_parent_type, id)
    if not process_parent:
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
        elif request.request == ActivationRequest.MONITOR:
            manager.monitor()
    except exceptions.MaxRunningProcessesError:
        return False
    except Exception as e:
        LOGGER.exception(
            f"Failed to process request {request.request} for "
            f"{process_parent_type} {process_parent.id}. Reason {str(e)}",
        )
    return True


def _make_user_request(
    process_parent_type: ProcessParentType,
    id: int,
    request_type: ActivationRequest,
    queue="activation",
) -> None:
    """Enqueue a task to manage the activation with the given id."""
    requests_queue.push(process_parent_type, id, request_type)
    job_id = _manage_process_job_id(process_parent_type, id)
    if not queue:
        queue = "activation"
    unique_enqueue(queue, job_id, _MANAGE_TASK, process_parent_type, id)


def start_rulebook_process(
    process_parent_type: ProcessParentType, id: int
) -> None:
    """Create a request to start the activation with the given id."""
    _make_user_request(process_parent_type, id, ActivationRequest.START, None)


def stop_rulebook_process(
    process_parent_type: ProcessParentType, id: int
) -> None:
    """Create a request to stop the activation with the given id."""
    queue = _get_queue_name(process_parent_type, id)
    _make_user_request(process_parent_type, id, ActivationRequest.STOP, queue)


def delete_rulebook_process(
    process_parent_type: ProcessParentType, id: int
) -> None:
    """Create a request to delete the activation with the given id."""
    queue = _get_queue_name(process_parent_type, id)
    _make_user_request(
        process_parent_type, id, ActivationRequest.DELETE, queue
    )


def restart_rulebook_process(
    process_parent_type: ProcessParentType, id: int
) -> None:
    """Create a request to restart the activation with the given id."""
    queue = _get_queue_name(process_parent_type, id)
    _make_user_request(
        process_parent_type, id, ActivationRequest.RESTART, queue
    )


def monitor_rulebook_process(
    process_parent_type: ProcessParentType, id: int
) -> None:
    """Create a request to monitor the activation with the given id."""
    queue = _get_queue_name(process_parent_type, id)
    _make_user_request(
        process_parent_type, id, ActivationRequest.MONITOR, queue
    )


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
        queue = _get_queue_name(process_parent_type, id)
        unique_enqueue(queue, job_id, _MANAGE_TASK, process_parent_type, id)

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
        queue = _get_queue_name(process_parent_type, id)
        unique_enqueue(queue, job_id, _MANAGE_TASK, process_parent_type, id)


def monitor_engine_events() -> None:
    """Monitor container engine events.

    Started by the scheduler, executed by the activation worker.
    It enqueues a monitor task for each activation when it ends
    """
    container_engine = new_container_engine(1, ProcessParentType.ACTIVATION)
    for event in container_engine.monitor_events():
        # monitor running instances
        LOGGER.info(f"Container engine event {event}")
        if event.reason in ["died", "Completed", "BackoffLimitExceeded"]:
            for process in models.RulebookProcess.objects.filter(
                status=ActivationStatus.RUNNING, activation_pod_id=event.name
            ):
                try:
                    process_parent_type = str(process.parent_type)
                    if process_parent_type == ProcessParentType.ACTIVATION:
                        id = process.activation_id
                    else:
                        id = process.event_stream_id
                    monitor_rulebook_process(process_parent_type, id)
                except Exception as e:
                    LOGGER.error(f"Monitor events error {e}")


def _get_queue_name(
    process_parent_type: ProcessParentType, id: int
) -> Optional[str]:
    obj = _get_process_parent(process_parent_type, id)
    if obj and obj.latest_instance and obj.latest_instance.queue:
        return obj.latest_instance.queue

    return "activation"


def _get_process_parent(process_parent_type: ProcessParentType, id: int):
    try:
        if process_parent_type == ProcessParentType.ACTIVATION:
            klass = Activation
        else:
            klass = EventStream
        return klass.objects.get(id=id)
    except ObjectDoesNotExist:
        LOGGER.warning(
            f"{process_parent_type} with {id} no longer exists, "
            "activation manager task will not be processed",
        )
    return None
