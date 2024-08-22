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
import random
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django_rq import get_queue

import aap_eda.tasks.activation_request_queue as requests_queue
from aap_eda.core import models
from aap_eda.core.enums import (
    ActivationRequest,
    ActivationStatus,
    ProcessParentType,
)
from aap_eda.core.models import Activation, ActivationRequestQueue
from aap_eda.core.tasking import Worker, unique_enqueue
from aap_eda.services.activation import exceptions
from aap_eda.services.activation.activation_manager import (
    ActivationManager,
    StatusManager,
)

from .exceptions import UnknownProcessParentType

LOGGER = logging.getLogger(__name__)


class HealthyQueueNotFoundError(Exception):
    """Raised when a queue is not found."""

    ...


def _manage_process_job_id(process_parent_type: str, id: int) -> str:
    """Return the unique job id for the activation manager task."""
    return f"{process_parent_type}-{id}"


def get_process_parent(
    process_parent_type: str,
    parent_id: int,
) -> Activation:
    if process_parent_type == ProcessParentType.ACTIVATION:
        klass = Activation
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
    process_parent: Activation,
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


def dispatch(
    process_parent_type: ProcessParentType,
    process_parent_id: int,
    request_type: Optional[ActivationRequest],
):
    job_id = _manage_process_job_id(process_parent_type, process_parent_id)
    # TODO: add "monitor" type to ActivationRequestQueue
    if request_type is None:
        request_type = "Monitor"

    LOGGER.info(
        f"Dispatching request {request_type} for {process_parent_type} "
        f"{process_parent_id}",
    )

    try:
        process_parent = get_process_parent(
            process_parent_type, process_parent_id
        )
    except ObjectDoesNotExist:
        LOGGER.warning(
            f"{process_parent_type} {process_parent_id} no longer exists, "
            f"request {request_type} can not be dispatched.",
        )
        return
    status_manager = StatusManager(process_parent)

    # new processes
    if request_type in [
        ActivationRequest.START,
        ActivationRequest.AUTO_START,
    ]:
        LOGGER.info(
            f"Dispatching {process_parent_type} "
            f"{process_parent_id} as new process.",
        )
        try:
            queue_name = get_least_busy_queue_name()
        except HealthyQueueNotFoundError:
            msg = (
                f"There are no healthy queues to process the start request "
                f"for {process_parent_type} {process_parent_id}. "
                "There may be an issue with the system; please contact "
                "the administrator."
            )
            LOGGER.warning(msg)
            status_manager.set_status(
                ActivationStatus.PENDING,
                msg,
            )
            return

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
                    "Scheduling request "
                    f"{request_type} for {process_parent_type} "
                    f"{process_parent_id} to the least busy queue; "
                    "it is not currently associated with a queue.",
                )
            else:
                LOGGER.info(
                    "Scheduling request"
                    f"{request_type} for {process_parent_type} "
                    f"{process_parent_id} to the least busy queue; "
                    f"its associated queue '{queue_name}' is from "
                    "previous configuation settings.",
                )
            try:
                queue_name = get_least_busy_queue_name()
            except HealthyQueueNotFoundError:
                msg = (
                    f"There are no healthy queues to process operation "
                    f"{request_type} for {process_parent_type} "
                    f"{process_parent_id}. Waiting for a worker. "
                    "There may be an issue with the system; please "
                    "contact the administrator."
                )
                LOGGER.warning(msg)
                status_manager.set_status(
                    ActivationStatus.PENDING,
                    msg,
                )
                return
        elif not check_rulebook_queue_health(queue_name):
            # The queue is unhealthy.  If we're not restarting it there's
            # nothing we can do except update its status to WORKERS_OFFLINE.
            if request_type != ActivationRequest.RESTART:
                # A process in PENDING status don't need to update its status.
                # A monitor can be scheduled for an activation in PENDING
                # status if its latest process is in workers-offline status
                # and it is scheduled for restart.
                if process_parent.status == ActivationStatus.PENDING:
                    return

                # If the process is in WORKERS_OFFLINE status, it is already
                # in a bad state.  We don't need to update its status.
                if process_parent.status == ActivationStatus.WORKERS_OFFLINE:
                    return

                msg = (
                    f"{process_parent_type} {process_parent_id} is in an "
                    "unknown state. The workers of its associated queue "
                    f"'{queue_name}' are failing liveness checks. "
                    "There may be an issue with the worker node; "
                    "please contact the administrator."
                )
                status_manager.set_status(
                    ActivationStatus.WORKERS_OFFLINE,
                    msg,
                )
                status_manager.set_latest_instance_status(
                    ActivationStatus.WORKERS_OFFLINE,
                    msg,
                )
                LOGGER.warning(msg)
                return

            # The queue is unhealthy, but this is a restart.
            # The priority is to adhere to the restart policy and
            # execute the task.
            LOGGER.warning(
                f"Restarting {process_parent_type} {process_parent_id} "
                "on the least busy queue; The workers of its associated queue "
                f"'{queue_name}' are failing liveness checks. "
                "There may be an issue with the worker node; please contact "
                "the administrator.",
            )
            try:
                queue_name = get_least_busy_queue_name()
            except HealthyQueueNotFoundError:
                msg = (
                    f"There are no healthy queues to process the "
                    f"restart request for {process_parent_type} "
                    f"{process_parent_id}. There may be an issue "
                    "with the system; please contact the administrator."
                )
                LOGGER.warning(msg)
                status_manager.set_status(
                    ActivationStatus.PENDING,
                    msg,
                )
                return

    unique_enqueue(
        queue_name,
        job_id,
        _manage,
        process_parent_type,
        process_parent_id,
    )


def get_least_busy_queue_name() -> str:
    """Return the queue name with the least running processes."""
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

    min_count = queue_counter.most_common()[-1][1]
    least_common = [
        queue for queue, count in queue_counter.items() if count == min_count
    ]
    if len(least_common) == 1:
        return least_common[0]
    return random.choice(least_common)


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
            ActivationStatus.WORKERS_OFFLINE,
        ]
    ):
        process_parent_type = str(process.parent_type)
        process_parent_id = process.activation_id

        dispatch(
            process_parent_type,
            process_parent_id,
            None,
        )


def enqueue_monitor_rulebook_processes() -> None:
    """Wrap monitor_rulebook_processes to ensure only one task is enqueued."""
    unique_enqueue(
        "default",
        "monitor_rulebook_processes",
        monitor_rulebook_processes,
    )
