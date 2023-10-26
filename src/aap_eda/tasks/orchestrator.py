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

from aap_eda.core import models
from aap_eda.core.enums import ActivationRequest, ActivationStatus
from aap_eda.core.tasking import unique_enqueue
from aap_eda.services.activation.manager import ActivationManager
from aap_eda.tasks.activation_request_queue import (
    list_activations,
    peek_all,
    pop_until,
    push,
)

logger = logging.getLogger(__name__)


def _manage_activation_job_id(activation_id: int) -> str:
    return f"activation-{activation_id}"


def _manage(activation_id: int):
    activation = models.Activation.objects.get(id=activation_id)
    has_user_requests = False
    pending_requests = peek_all(activation_id)
    while pending_requests:
        for request in pending_requests:
            manager = ActivationManager(activation)
            if request.request == ActivationRequest.START:
                manager.start()
            elif request.request == ActivationRequest.STOP:
                manager.stop()
            elif request.request == ActivationRequest.RESTART:
                manager.restart()
            elif request.request == ActivationRequest.DELETE:
                pass  # manager.delete()
            pop_until(activation_id, request.id)
        has_user_requests = True
        pending_requests = peek_all(activation_id)

    if not has_user_requests:
        ActivationManager(activation).monitor()


def _make_user_request(activation_id: int, request_type: ActivationRequest):
    push(activation_id, request_type)
    job_id = _manage_activation_job_id(activation_id)
    unique_enqueue("activation", job_id, _manage, activation_id)


def start_activation(activation_id: int):
    _make_user_request(activation_id, ActivationRequest.START)


def stop_activation(activation_id: int):
    _make_user_request(activation_id, ActivationRequest.START)


def delete_activation(activation_id: int):
    _make_user_request(activation_id, ActivationRequest.DELETE)


def restart_activation(activation_id: int):
    _make_user_request(activation_id, ActivationRequest.RESTART)


# Started by the scheduler, executed by the default worker
def monitor_activations() -> None:
    # run pending user requests
    for activation_id in list_activations():
        job_id = _manage_activation_job_id(activation_id)
        unique_enqueue("activation", job_id, _manage, activation_id)

    # monitor running instances
    for activation in models.Activation.objects.filter(
        status=ActivationStatus.RUNNING
    ):
        job_id = _manage_activation_job_id(activation.id)
        unique_enqueue("activation", job_id, _manage, activation.id)
