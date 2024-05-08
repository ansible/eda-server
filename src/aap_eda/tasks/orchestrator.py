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
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional, Union

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django_rq import get_queue
from rq import Worker

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
from aap_eda.services.activation.activation_manager import (
    ActivationManager,
    StatusManager,
)

LOGGER = logging.getLogger(__name__)


class HealthyQueueNotFoundError(Exception):
    """Raised when a queue is not found."""

    ...


class UnknownProcessParentType(Exception):
    """Raised when the process parent type is unknown."""

    ...


def _manage_process_job_id(process_parent_type: str, id: int) -> str:
    """Return the unique job id for the activation manager task."""
    return f"{process_parent_type}-{id}"


def get_process_parent(
    process_parent_type: str,
    parent_id: int,
) -> Union[Activation, EventStream]:
    if process_parent_type == ProcessParentType.ACTIVATION:
        klass = Activation
    elif process_parent_type == ProcessParentType.EVENT_STREAM:
        klass = EventStream
    else:
        raise UnknownProcessParentType(
            f"Unknown process parent type {process_parent_type}",
        )

    return klass.objects.get(id=parent_id)


def _manage(process_parent_type: str, id: int) -> None:
    """Manage the activation with the given id.

    It will run pending user requests or monitor the activation
    if there are no pending requests.
    """
    try:
        process_parent = get_process_parent(process_parent_type, id)
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

    if not has_request_processed and process_parent.status in [
        ActivationStatus.RUNNING,
        ActivationStatus.WORKERS_OFFLINE,
    ]:
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
    manager = ActivationManager(process_parent)
    if (
        request.request in start_commands
        and not manager.check_new_process_allowed()
    ):
        return False

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
        LOGGER.error(
            f"Failed to process request {request.request} for "
            f"{process_parent_type} {process_parent.id}. Reason {str(e)}",
            exc_info=settings.DEBUG,
        )
    return True


def _set_request_cannot_be_run_status(
    request_type: ActivationRequest,
    process_parent_type: ProcessParentType,
    process_parent_id: int,
    status_text: str,
) -> None:
    """Set the request status to indicate it cannot be run on this node.

    The request cannot be run on this node due to detected functional issues.
    While it cannot be run on this node anothter functional node can run it.
    This method sets the request's state such that other nodes can identify
    it as something to be run, if possible.  This identification is performed
    as part of monitor_rulebook_processes.
    """
    status_manager = StatusManager(
        get_process_parent(process_parent_type, process_parent_id),
    )

    status = ActivationStatus.WORKERS_OFFLINE
    # If the request is start/auto-start we know the request isn't
    # running.
    # If the request is in one of the pending states that also
    # indicates it's not running; this check is for previous
    # failures to start that got dispatched from the monitor
    # task.
    if (
        request_type
        in [
            ActivationRequest.START,
            ActivationRequest.AUTO_START,
        ]
    ) or (
        status_manager.db_instance.status
        in [
            ActivationStatus.PENDING,
            ActivationStatus.PENDING_WORKERS_OFFLINE,
        ]
    ):
        status = ActivationStatus.PENDING_WORKERS_OFFLINE

    status_manager.set_status(status, status_text)
    # There may not be a latest instance.
    if status_manager.latest_instance:
        status_manager.set_latest_instance_status(status, status_text)


def dispatch(
    process_parent_type: ProcessParentType,
    process_parent_id: int,
    request_type: Optional[ActivationRequest],
):
    # TODO: add "monitor" type to ActivationRequestQueue
    if request_type is None:
        request_type = "Monitor"

    job_id = _manage_process_job_id(process_parent_type, process_parent_id)
    LOGGER.info(
        f"Dispatching request type {request_type} for"
        f" {process_parent_type} {process_parent_id}",
    )

    queue_name = None
    enqueable = True

    # new processes
    if request_type in [
        ActivationRequest.START,
        ActivationRequest.AUTO_START,
    ]:
        LOGGER.info(
            f"Dispatching {process_parent_type} {process_parent_id}"
            " as new process.",
        )
    else:
        queue_name = get_queue_name_by_parent_id(
            process_parent_type,
            process_parent_id,
        )

        # If there is not an associated queue or the queue does not exist
        # within the configured queues (i.e., it is from a previous deployment
        # with different queues) we get a queue to use.
        if (not queue_name) or (
            queue_name not in settings.RULEBOOK_WORKER_QUEUES
        ):
            if not queue_name:
                LOGGER.info(
                    "Scheduling request"
                    f" type {request_type} for {process_parent_type}"
                    f" {process_parent_id} to the least busy queue"
                    "; it is not currently associated with a queue.",
                )
            else:
                LOGGER.info(
                    "Scheduling request"
                    f" type {request_type} for {process_parent_type}"
                    f" {process_parent_id} to the least busy queue"
                    f"; its associated queue '{queue_name}' is from"
                    " previous configuation settings.",
                )
            queue_name = None

    status_msg = (
        f"{process_parent_type} {process_parent_id} is in an "
        "unknown state. The workers of its associated queue "
        f"'{queue_name}' are failing liveness checks. "
        "There may be an issue with the node; please contact "
        "the administrator."
    )
    if queue_name and (not check_rulebook_queue_health(queue_name)):
        # The queue is unhealthy; log this fact.
        # If it's a restart we'll try a different queue below.
        LOGGER.warning(status_msg)

        if request_type == ActivationRequest.RESTART:
            queue_name = None

            LOGGER.warning(
                "Request"
                f" type {request_type} for {process_parent_type}"
                f" {process_parent_id} will be run on the least busy queue."
            )
        else:
            enqueable = False

    if enqueable and (not queue_name):
        try:
            queue_name = get_least_busy_queue_name()
        except HealthyQueueNotFoundError:
            enqueable = False
            status_msg = (
                f"The workers for request type {request_type}"
                f" for {process_parent_type} {process_parent_id}"
                " are failing liveness checks.  There may be an"
                " issue with the node; please contact the administrator."
            )

    if not enqueable:
        # The request is not enqueable.  If not a restart set the request
        # status to "workers offline".
        if request_type != ActivationRequest.RESTART:
            # Set the request status such that, if possible, a functional
            # node can pick it up and run it.
            _set_request_cannot_be_run_status(
                request_type,
                process_parent_type,
                process_parent_id,
                status_msg,
            )
    else:
        unique_enqueue(
            queue_name,
            job_id,
            _manage,
            process_parent_type,
            process_parent_id,
        )


def get_least_busy_queue_name() -> str:
    """Return the queue name with the least running processes."""
    if len(settings.RULEBOOK_WORKER_QUEUES) == 1:
        return settings.RULEBOOK_WORKER_QUEUES[0]

    queue_counter = Counter()

    for queue_name in settings.RULEBOOK_WORKER_QUEUES:
        if not check_rulebook_queue_health(queue_name):
            continue
        running_processes_count = models.RulebookProcess.objects.filter(
            status__in=[ActivationStatus.RUNNING, ActivationStatus.STARTING],
            rulebookprocessqueue__queue_name=queue_name,
        ).count()
        queue_counter[queue_name] = running_processes_count

    if not queue_counter:
        raise HealthyQueueNotFoundError(
            "No healthy queue found to dispatch the request",
        )

    return queue_counter.most_common()[-1][0]


def get_queue_name_by_parent_id(
    process_parent_type: ProcessParentType,
    process_parent_id: int,
) -> Optional[str]:
    """Return the queue name associated with the process ID."""
    try:
        parent_process = get_process_parent(
            process_parent_type,
            process_parent_id,
        )
        process = parent_process.latest_instance
    except ObjectDoesNotExist:
        raise ValueError(
            f"No {process_parent_type} found with ID {process_parent_id}"
        ) from None
    except models.RulebookProcess.DoesNotExist:
        raise ValueError(
            f"No RulebookProcess found with ID {process_parent_id}"
        ) from None
    except models.RulebookProcessQueue.DoesNotExist:
        raise ValueError(
            "No Queue associated with RulebookProcess ID "
            f"{process_parent_id}",
        ) from None
    if not hasattr(process, "rulebookprocessqueue"):
        return None
    return process.rulebookprocessqueue.queue_name


def check_rulebook_queue_health(queue_name: str) -> bool:
    """Check for the state of the queue.

    Returns True if the queue is healthy, False otherwise.
    Clears the queue if all workers are dead to avoid stuck processes.
    """
    queue = get_queue(queue_name)

    all_workers_dead = True
    for worker in Worker.all(queue=queue):
        last_heartbeat = worker.last_heartbeat
        if last_heartbeat is None:
            continue
        threshold = datetime.now() - timedelta(
            seconds=settings.DEFAULT_WORKER_HEARTBEAT_TIMEOUT,
        )
        if last_heartbeat >= threshold:
            all_workers_dead = False
            break

    if all_workers_dead:
        queue.empty()
        return False

    return True


# Internal start/restart requests are sent by the manager in restart_helper.py
def start_rulebook_process(
    process_parent_type: ProcessParentType,
    process_parent_id: int,
) -> None:
    """Create a request to start the activation with the given id."""
    requests_queue.push(
        process_parent_type,
        process_parent_id,
        ActivationRequest.START,
    )
    dispatch(
        process_parent_type,
        process_parent_id,
        ActivationRequest.START,
    )


def stop_rulebook_process(
    process_parent_type: ProcessParentType,
    process_parent_id: int,
) -> None:
    """Create a request to stop the activation with the given id."""
    requests_queue.push(
        process_parent_type,
        process_parent_id,
        ActivationRequest.STOP,
    )
    dispatch(
        process_parent_type,
        process_parent_id,
        ActivationRequest.STOP,
    )


def delete_rulebook_process(
    process_parent_type: ProcessParentType,
    process_parent_id: int,
) -> None:
    """Create a request to delete the activation with the given id."""
    requests_queue.push(
        process_parent_type,
        process_parent_id,
        ActivationRequest.DELETE,
    )
    dispatch(
        process_parent_type,
        process_parent_id,
        ActivationRequest.DELETE,
    )


def restart_rulebook_process(
    process_parent_type: ProcessParentType,
    process_parent_id: int,
) -> None:
    """Create a request to restart the activation with the given id."""
    requests_queue.push(
        process_parent_type,
        process_parent_id,
        ActivationRequest.RESTART,
    )
    dispatch(
        process_parent_type,
        process_parent_id,
        ActivationRequest.RESTART,
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
    for request in requests_queue.list_requests():
        dispatch(
            request.process_parent_type,
            request.process_parent_id,
            request.request,
        )

    # monitor running instances
    for process in models.RulebookProcess.objects.filter(
        status__in=[
            ActivationStatus.RUNNING,
            ActivationStatus.PENDING_WORKERS_OFFLINE,
            ActivationStatus.WORKERS_OFFLINE,
        ]
    ):
        process_parent_type = str(process.parent_type)
        if process_parent_type == ProcessParentType.ACTIVATION:
            process_parent_id = process.activation_id
        else:
            process_parent_id = process.event_stream_id
        dispatch(
            process_parent_type,
            process_parent_id,
            None,
        )
