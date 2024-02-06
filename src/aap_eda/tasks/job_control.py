#  Copyright 2024 Red Hat, Inc.
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

import aap_eda.tasks.activation_request_queue as requests_queue
from aap_eda.core.enums import ActivationRequest

# from aap_eda.core.tasking import unique_enqueue # noqa: E800

LOGGER = logging.getLogger(__name__)


class JobControl(abc.ABC):
    def __init__(self, id: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = id

    # TODO(jshimkus): create an abstract RequestQueue.
    @classmethod
    @abc.abstractmethod
    def queue(cls) -> type[requests_queue]:
        """Return the queue used for the job."""
        ...

    @classmethod
    @abc.abstractmethod
    def queue_name(cls) -> str:
        """Return the name of the queue used for the job."""
        ...

    @property
    @abc.abstractmethod
    def job_id(self) -> str:
        """Return the unique job id."""
        ...

    # TDOO(jshimkus) - Abstract the request type.
    def _make_request(self, request_type: ActivationRequest) -> None:
        """Enqueue a task to manage the job."""
        self.queue().push(self.id, request_type)
        # TODO(jshimkus) - We want to encapsulate the _manage functionality
        # but there are aspects relating to long-term monitoring to work
        # out.
        #
        # unique_enqueue(                                       # noqa: E800
        #    self.queue_name(), self.job_id, _manage, self.id   # noqa: E800
        # )                                                     # noqa: E800

    @abc.abstractmethod
    def make_delete_request(self) -> None:
        """Create a request to delete the job."""
        ...

    @abc.abstractmethod
    def make_restart_request(self) -> None:
        """Create a request to restart the job."""
        ...

    @abc.abstractmethod
    def make_start_request(self) -> None:
        """Create a request to start the job."""
        ...

    @abc.abstractmethod
    def make_stop_request(self) -> None:
        """Create a request to stop the job."""
        ...


class ActivationControl(JobControl):
    @classmethod
    def queue(cls) -> type[requests_queue]:
        return requests_queue

    @classmethod
    def queue_name(cls) -> str:
        return "activation"

    @property
    def job_id(self) -> str:
        return f"activation-{self.id}"

    def make_delete_request(self) -> None:
        self._make_request(ActivationRequest.DELETE)

    def make_restart_request(self) -> None:
        self._make_request(ActivationRequest.RESTART)

    def make_start_request(self) -> None:
        self._make_request(ActivationRequest.START)

    def make_stop_request(self: int) -> None:
        self._make_request(ActivationRequest.STOP)
