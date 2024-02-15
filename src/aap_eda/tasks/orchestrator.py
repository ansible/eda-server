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

import abc
import logging
import typing

from django.conf import settings

import aap_eda.tasks.activation_request_queue as requests_queue
from aap_eda.core import models
from aap_eda.core.enums import ActivationRequest, ActivationStatus
from aap_eda.core.tasking import unique_enqueue
from aap_eda.services.activation.manager import ActivationManager

LOGGER = logging.getLogger(__name__)


class Orchestrator(abc.ABC):
    def __init__(self, id: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = id

    def enqueue(self) -> None:
        unique_enqueue(self._queue_name(), self.job_id, self.manage, self.id)

    @staticmethod
    @abc.abstractmethod
    def manage(object_id: int) -> None:
        """Manage the requests for the given id.

        It will run pending user requests or monitor running requests
        if there are no pending requests.
        """
        ...

    # TODO(jshimkus): create an abstract RequestQueue.
    @classmethod
    @abc.abstractmethod
    def queue(cls) -> type[requests_queue]:
        """Return the queue used for the requests."""
        ...

    @property
    @abc.abstractmethod
    def job_id(self) -> str:
        """Return the unique request id."""
        ...

    @abc.abstractmethod
    def delete_job(self) -> None:
        """Create a request to delete the job."""
        ...

    @abc.abstractmethod
    def restart_job(self) -> None:
        """Create a request to restart the job."""
        ...

    @abc.abstractmethod
    def start_job(self) -> None:
        """Create a request to start the job."""
        ...

    @abc.abstractmethod
    def stop_job(self) -> None:
        """Create a request to stop the job."""
        ...

    @classmethod
    @abc.abstractmethod
    def _can_start_new_job(cls, object: typing.Any) -> bool:
        ...
        num_running_activations = models.Activation.objects.filter(
            status__in=[ActivationStatus.RUNNING, ActivationStatus.STARTING],
        ).count()
        if num_running_activations >= settings.MAX_RUNNING_ACTIVATIONS:
            LOGGER.info(
                "No capacity to start a new activation. "
                f"Activation {object.id} is postponed",
            )
            return False
        return True

    # TODO(jshimkus) - Abstract the object type.
    @classmethod
    def _manage(cls, object: typing.Any) -> bool:
        """Run pending user requests, if any.

        Returns a boolean indicating if one or more pending requests
        where run.
        """
        has_request_processed = False
        while_condition = True
        while while_condition:
            pending_requests = cls.queue().peek_all(object.id)
            while_condition = bool(pending_requests)
            for request in pending_requests:
                if cls._run_request(object, request):
                    cls.queue().pop_until(object.id, request.id)
                    has_request_processed = True
                else:
                    while_condition = False
                    break
        return has_request_processed

    # TODO(jshimkus) - Abstract the request type.
    def _make_request(self, request_type: ActivationRequest) -> None:
        """Enqueue a task to run the job."""
        self.queue().push(self.id, request_type)
        self.enqueue()

    @classmethod
    @abc.abstractmethod
    def _queue_name(cls) -> str:
        """Return the name of the queue used for the requests."""
        ...

    @classmethod
    @abc.abstractmethod
    def _run_request(cls, object: typing.Any, request: typing.Any) -> bool:
        ...


class ActivationOrchestrator(Orchestrator):
    @staticmethod
    def manage(object_id: int) -> None:
        try:
            activation = models.Activation.objects.get(id=object_id)
        except models.Activation.DoesNotExist:
            LOGGER.warning(
                f"Activation {object_id} no longer exists, "
                "activation manager task will not be processed",
            )
            return

        if (
            not ActivationOrchestrator._manage(activation)
            and activation.status == ActivationStatus.RUNNING
        ):
            LOGGER.info(
                f"Processing monitor request for activation {activation.id}",
            )
            ActivationManager(activation).monitor()

    @classmethod
    def queue(cls) -> type[requests_queue]:
        return requests_queue

    @property
    def job_id(self) -> str:
        return f"activation-{self.id}"

    def delete_job(self) -> None:
        self._make_request(ActivationRequest.DELETE)

    def restart_job(self) -> None:
        self._make_request(ActivationRequest.RESTART)

    def start_job(self) -> None:
        self._make_request(ActivationRequest.START)

    def stop_job(self: int) -> None:
        self._make_request(ActivationRequest.STOP)

    @classmethod
    def _can_start_new_job(cls, object: typing.Any) -> bool:
        num_running_activations = models.Activation.objects.filter(
            status__in=[ActivationStatus.RUNNING, ActivationStatus.STARTING],
        ).count()
        if num_running_activations >= settings.MAX_RUNNING_ACTIVATIONS:
            LOGGER.info(
                "No capacity to start a new activation. "
                f"Activation {object.id} is postponed",
            )
            return False
        return True

    @classmethod
    def _queue_name(cls) -> str:
        return "activation"

    @classmethod
    def _run_request(cls, object: typing.Any, request: typing.Any) -> bool:
        """Attempt to run a request for an activation via the manager."""
        LOGGER.info(
            f"Processing request {request.request} for activation "
            f"{object.id}",
        )
        start_commands = [
            ActivationRequest.START,
            ActivationRequest.AUTO_START,
        ]
        if request.request in start_commands and not cls._can_start_new_job(
            object,
        ):
            return False

        manager = ActivationManager(object)
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
                f"activation {object.id}. Reason {str(e)}",
            )
        return True


def monitor_activations() -> None:
    """Monitor activations scheduled task.

    Started by the scheduler, executed by the default worker.
    It enqueues a task for each job that needs to be managed.
    Handles both user requests and monitoring of running jobs.
    It will not enqueue a task if there is already one for the same
    job.
    """
    # run pending user requests
    for activation_id in ActivationOrchestrator.queue().list_activations():
        ActivationOrchestrator(activation_id).enqueue()

    # monitor running instances
    for activation in models.Activation.objects.filter(
        status=ActivationStatus.RUNNING,
    ):
        ActivationOrchestrator(activation.id).enqueue()
