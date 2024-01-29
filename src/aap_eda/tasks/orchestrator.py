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
from typing import Any

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils.module_loading import import_string

import aap_eda.tasks.activation_request_queue as requests_queue
from aap_eda.core.enums import ActivationRequest, ActivationStatus
from aap_eda.core.models import ActivationRequestQueue
from aap_eda.core.tasking import unique_enqueue
from aap_eda.services.activation.manager import (
    ActivationManager as RulebookManager,
)

LOGGER = logging.getLogger(__name__)

MONITOR_CLASSES = {
    "aap_eda.core.models.Activation": import_string(
        "aap_eda.core.models.Activation"
    )
}


def _manage_activation_job_id(klass: str, activation_id: int) -> str:
    """Return the unique job id for the activation manager task."""
    return f"{klass}-{activation_id}"


def _manage(name: str, instance_id: int) -> None:
    """Manage the activation with the given id.

    It will run pending user requests or monitor the activation
    if there are no pending requests.
    """
    try:
        klass = import_string(name)
        obj = klass.objects.get(id=instance_id)
    except ObjectDoesNotExist:
        LOGGER.warning(
            f"{name} with id {instance_id} no longer exists, "
            "activation manager task will not be processed",
        )
        return

    has_request_processed = False
    while_condition = True
    while while_condition:
        pending_requests = requests_queue.peek_all(instance_id, name)
        while_condition = bool(pending_requests)
        for request in pending_requests:
            if _run_request(klass, obj, request):
                requests_queue.pop_until(instance_id, name, request.id)
                has_request_processed = True
            else:
                while_condition = False
                break

    if not has_request_processed and obj.status == ActivationStatus.RUNNING:
        LOGGER.info(
            f"Processing monitor request for {name} {instance_id}",
        )
        RulebookManager(obj).monitor()


def _run_request(
    klass,
    obj: Any,
    request: ActivationRequestQueue,
) -> bool:
    """Attempt to run a request for an activation via the manager."""
    LOGGER.info(
        f"Processing request {request.request} for {type(obj)} {obj.id}"
    )
    start_commands = [ActivationRequest.START, ActivationRequest.AUTO_START]
    if request.request in start_commands and not _can_start_new_activation(
        klass, obj
    ):
        return False

    manager = RulebookManager(obj)
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
            f"{type(obj)} id {obj.id}. Reason {str(e)}",
        )
    return True


def _can_start_new_activation(klass, obj) -> bool:
    num_running_activations = klass.objects.filter(
        status__in=[ActivationStatus.RUNNING, ActivationStatus.STARTING],
    ).count()
    if num_running_activations >= settings.MAX_RUNNING_ACTIVATIONS:
        LOGGER.info(
            "No capacity to start a new activation. "
            f"{obj.type} {obj.id} is postponed",
        )
        return False
    return True


def _make_user_request(
    instance_id: int,
    name: str,
    request_type: ActivationRequest,
) -> None:
    """Enqueue a task to manage the activation with the given id."""
    requests_queue.push(instance_id, name, request_type)
    job_id = _manage_activation_job_id(name, instance_id)
    unique_enqueue(
        "activation",
        job_id,
        _manage,
        **{"name": name, "instance_id": instance_id},
    )


def start_activation(instance_id: int, name: str) -> None:
    """Create a request to start the activation with the given id."""
    _make_user_request(instance_id, name, ActivationRequest.START)


def stop_activation(instance_id: int, name: str) -> None:
    """Create a request to stop the activation with the given id."""
    _make_user_request(instance_id, name, ActivationRequest.STOP)


def delete_activation(instance_id: int, name: str) -> None:
    """Create a request to delete the activation with the given id."""
    _make_user_request(instance_id, name, ActivationRequest.DELETE)


def restart_activation(instance_id: int, name: str) -> None:
    """Create a request to restart the activation with the given id."""
    _make_user_request(instance_id, name, ActivationRequest.RESTART)


def monitor_activations() -> None:
    """Monitor activations scheduled task.

    Started by the scheduler, executed by the default worker.
    It enqueues a task for each activation that needs to be managed.
    Handles both user requests and monitoring of running activations.
    It will not enqueue a task if there is already one for the same
    activation.
    """
    # run pending user requests
    for name, instance_id in requests_queue.list_activations():
        job_id = _manage_activation_job_id(name, instance_id)
        unique_enqueue(
            "activation",
            job_id,
            _manage,
            **{"name": name, "instance_id": instance_id},
        )

    # monitor running instances
    for name, klass in MONITOR_CLASSES.items():
        for obj in klass.objects.filter(
            status=ActivationStatus.RUNNING,
        ):
            job_id = _manage_activation_job_id(name, obj.id)
            unique_enqueue(
                "activation",
                job_id,
                _manage,
                **{"name": name, "instance_id": obj.id},
            )
