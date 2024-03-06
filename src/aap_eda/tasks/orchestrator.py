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
from typing import Optional, Union

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django_rq import get_queue
from rq import get_current_job

import aap_eda.tasks.activation_request_queue as requests_queue
from aap_eda.core import models
from aap_eda.core.enums import (
    ActivationRequest,
    ActivationStatus,
    ProcessParentType,
)
from aap_eda.core.models import Activation, ActivationRequestQueue, EventStream
from aap_eda.core.tasking import Queue, unique_enqueue
from aap_eda.services.activation import exceptions
from aap_eda.services.activation.manager import ActivationManager

LOGGER = logging.getLogger(__name__)


def _manage_process_job_id(process_parent_type: str, id: int) -> str:
    """Return the unique job id for the activation manager task."""
    return f"{process_parent_type}-{id}"


def get_process_parent(
    process_parent_type: str,
    parent_id: int,
) -> Union[Activation, EventStream]:
    if process_parent_type == ProcessParentType.ACTIVATION:
        klass = Activation
    else:
        klass = EventStream
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
    this_job = get_current_job()
    if (
        request.request in start_commands
        and not ActivationManager.check_new_process_allowed(
            process_parent_type,
            process_parent.id,
            this_job.origin,
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


class QueueNotFoundError(Exception):
    """Raised when a queue is not found."""

    ...


class RequestDispatcher:
    """Dispatch process requests to the activation manager.

    Handles the dispatch of requests for the orchestrator,
    enqueueing the RQ task in the right queue.
    """

    _queues = None

    @classmethod
    @property
    def queues(cls):
        if cls._queues is None:
            cls._queues = cls.get_queues()
        return cls._queues

    @staticmethod
    def dispatch(
        process_parent_type: ProcessParentType,
        process_parent_id: int,
        request_type: Optional[ActivationRequest],
    ):
        job_id = _manage_process_job_id(process_parent_type, process_parent_id)

        if request_type in [
            ActivationRequest.START,
            ActivationRequest.AUTO_START,
        ]:
            queue_name = RequestDispatcher.get_most_free_queue_name()
        else:
            queue_name = RequestDispatcher.get_queue_name_by_parent_id(
                process_parent_type,
                process_parent_id,
            )

            # If the queue is old or doesn't exist, we use a valid one
            # to make sure the request is processed and the restart
            # policy is respected
            if (
                not queue_name
                or queue_name not in settings.RULEBOOK_WORKER_QUEUES
            ):
                queue_name = RequestDispatcher.get_most_free_queue_name()

        unique_enqueue(
            queue_name,
            job_id,
            _manage,
            process_parent_type,
            process_parent_id,
        )

    @staticmethod
    def get_queues() -> list[Queue]:
        """Return the list of RQ queues configured for podman multinode."""
        queues = []
        for queue_name in settings.RULEBOOK_WORKER_QUEUES:
            try:
                queues.append(get_queue(queue_name))
            except KeyError:
                LOGGER.exception(f"Queue {queue_name} not found")
                raise QueueNotFoundError(
                    f"Queue {queue_name} not found"
                ) from None

        return queues

    @staticmethod
    def get_most_free_queue_name() -> str:
        """Return the queue name with the least running processes."""
        if not RequestDispatcher.queues:
            raise QueueNotFoundError("No queues found")

        if len(RequestDispatcher.queues) == 1:
            return RequestDispatcher.queues[0].name

        queue_counter = Counter()

        for queue in RequestDispatcher.queues:
            running_processes_count = models.RulebookProcess.objects.filter(
                status=ActivationStatus.RUNNING,
                rulebookprocessqueue__queue_name=queue.name,
            ).count()
            queue_counter[queue.name] = running_processes_count
        return queue_counter.most_common()[-1][0]

    @staticmethod
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
    RequestDispatcher.dispatch(
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
    RequestDispatcher.dispatch(
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
    RequestDispatcher.dispatch(
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
    RequestDispatcher.dispatch(
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
        RequestDispatcher.dispatch(
            request.process_parent_type,
            request.process_parent_id,
            request.request,
        )

    # monitor running instances
    for process in models.RulebookProcess.objects.filter(
        status=ActivationStatus.RUNNING,
    ):
        process_parent_type = str(process.parent_type)
        if process_parent_type == ProcessParentType.ACTIVATION:
            process_parent_id = process.activation_id
        else:
            process_parent_id = process.event_stream_id
        RequestDispatcher.dispatch(
            process_parent_type,
            process_parent_id,
            None,
        )
