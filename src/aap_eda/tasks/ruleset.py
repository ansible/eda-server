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
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rq.worker import Worker, WorkerStatus

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus, RestartPolicy
from aap_eda.core.tasking import get_queue, job, job_from_queue, unique_enqueue
from aap_eda.services.ruleset.activate_rulesets import (
    ActivateRulesets,
    save_activation_and_instance,
)
from aap_eda.services.ruleset.activation_db_logger import ActivationDbLogger

logger = logging.getLogger(__name__)


def activate(
    activation_id: int, requester: str = "User", reconnect: bool = False
) -> None:
    job_id = _activation_job_id(activation_id)
    unique_enqueue(
        "activation", job_id, _activate, activation_id, requester, reconnect
    )


def _activation_job_id(activation_id: int) -> str:
    return f"activation-{activation_id}"


def _activate(
    activation_id: int, requester: str = "User", reconnect: bool = False
) -> None:
    action = "Reconnecting" if reconnect else "Activating"
    logger.info(
        f"{action} activation id: {activation_id} requested " f"by {requester}"
    )

    job = job_from_queue(
        get_queue("activation"), _activation_job_id(activation_id)
    )

    with transaction.atomic():
        activation = (
            models.Activation.objects.select_for_update()
            .filter(id=activation_id)
            .first()
        )
        if not activation or activation.status == ActivationStatus.DELETING:
            logger.info(f"Activation id: {activation_id} is deleted")
            return

        if not activation.is_enabled:
            logger.info(f"Activation id: {activation_id} is disabled")
            return

        activation.worker_name = job.worker_name
        update_fields = ["worker_name", "modified_at"]
        if not reconnect:
            activation.status = ActivationStatus.STARTING
            update_fields.append("status")

            # Note: expect scheduler to set requester as "SCHEDULER"
            if requester == "SCHEDULER":
                activation.restart_count += 1
                update_fields.append("restart_count")

        activation.save(update_fields=update_fields)

    ActivateRulesets().activate(activation, reconnect)

    logger.info(f"Activation {activation.name} is done.")


@job("default")
def deactivate(
    activation_id: int,
    requester: str = "User",
    delete: bool = False,
) -> None:
    logger.info(
        f"Disabling activation id: {activation_id} requested by {requester}"
    )

    with transaction.atomic():
        activation = (
            models.Activation.objects.select_for_update()
            .filter(id=activation_id)
            .first()
        )
        if not activation:
            logger.warning(f"Activation {activation_id} is deleted.")
            return

        if activation.status in [
            ActivationStatus.COMPLETED,
            ActivationStatus.FAILED,
            ActivationStatus.STOPPED,
        ]:
            logger.warning(
                f"Cannot deactivate the activation {activation.name} when its "
                f"status is {activation.status}"
            )
            return

        final_status = (
            ActivationStatus.FAILED
            if requester == "SCHEDULER"
            else ActivationStatus.STOPPED
        )
        _perform_deactivate(activation, final_status)

        if delete:
            logger.info(f"Activation {activation.name} is deleted")
            activation.delete()
        else:
            activation.status = final_status
            activation.save(update_fields=["status", "modified_at"])


@job("default")
def restart(activation_id: int, requester: str = "User") -> None:
    logger.info(
        f"Restarting activation id: {activation_id} requested by {requester}"
    )

    with transaction.atomic():
        activation = (
            models.Activation.objects.select_for_update()
            .filter(id=activation_id)
            .first()
        )
        if not activation:
            logger.warning(f"Activation {activation_id} is deleted.")
            return

        if activation.status not in [
            ActivationStatus.COMPLETED,
            ActivationStatus.FAILED,
            ActivationStatus.STOPPED,
        ]:
            _perform_deactivate(activation, ActivationStatus.STOPPED)

        activation.refresh_from_db()
        if activation.status in [
            ActivationStatus.STOPPING,
            ActivationStatus.DELETING,
        ]:
            logger.warning(
                f"Cannot restart the activation {activation.name} when its "
                f"status is {activation.status}"
            )
            return

        activation.status = ActivationStatus.PENDING
        activation.save(update_fields=["status", "modified_at"])

        activate(activation.id, requester)


def _perform_deactivate(
    activation: models.Activation, final_status: ActivationStatus
) -> None:
    logger.info(f"Task started: Deactivate Activation ({activation.name})")

    # clear the job from rq if it's pending/running
    job_id = _activation_job_id(activation.id)

    if job_id:
        queue = get_queue(name="activation")
        job = job_from_queue(queue, job_id)
        if job:
            job.cancel()
            logger.info(
                f"The job: {job.id} for activation: {activation.name}"
                f" is canceled from the queue: {queue.name}"
            )

    # deactivate activation instance if available
    current_instances = (
        models.ActivationInstance.objects.select_for_update().filter(
            activation_id=activation.id,
            status__in=[
                ActivationStatus.STARTING,
                ActivationStatus.PENDING,
                ActivationStatus.RUNNING,
                ActivationStatus.UNRESPONSIVE,
            ],
        )
    )

    for instance in current_instances:
        activation_db_logger = ActivationDbLogger(instance.id)
        activation_db_logger.write(
            lines=f"Start to disable instance {instance.id} ...",
            flush=True,
        )

        ActivateRulesets().deactivate(
            instance=instance, final_status=final_status
        )


# Started by the scheduler, executed by the default worker
def monitor_activations() -> None:
    job_id = "monitor_activations"
    unique_enqueue("default", job_id, _monitor_activations, at_front=True)


def _monitor_activations() -> None:
    logger.info("Task started: monitor_activations")
    now = timezone.now()
    activations_in_reconnecting = _reconnect_activations()
    _detect_unresponsive(now, activations_in_reconnecting)
    _stop_unresponsive(now)
    _start_completed(now)
    _start_failed(now)


def _detect_unresponsive(
    now: timezone.datetime, activations_in_reconnecting: list[int]
) -> None:
    running_statuses = [
        ActivationStatus.RUNNING,
        ActivationStatus.STARTING,
    ]
    cutoff_time = now - timedelta(
        seconds=settings.RULEBOOK_LIVENESS_TIMEOUT_SECONDS
    )
    for instance in models.ActivationInstance.objects.filter(
        status__in=running_statuses, updated_at__lt=cutoff_time
    ).exclude(activation__in=activations_in_reconnecting):
        instance.status = ActivationStatus.UNRESPONSIVE
        instance.updated_at = now
        save_activation_and_instance(instance, ["status", "updated_at"])


def _stop_unresponsive(now: timezone.datetime) -> None:
    for activation in models.Activation.objects.filter(
        status=ActivationStatus.UNRESPONSIVE,
    ):
        logger.info(
            f"Deactivate activation {activation.name} due to lost heartbeat"
        )
        deactivate(
            activation_id=activation.id,
            requester="SCHEDULER",
            delete=False,
        )


def _start_completed(now: timezone.datetime):
    cutoff_time = now - timedelta(
        seconds=settings.ACTIVATION_RESTART_SECONDS_ON_COMPLETE
    )
    for activation in models.Activation.objects.filter(
        is_enabled=True,
        status=ActivationStatus.COMPLETED,
        restart_policy=RestartPolicy.ALWAYS,
        status_updated_at__lt=cutoff_time,
    ):
        logger.info(
            f"Restart activation {activation.name} according to its restart"
            " policy."
        )
        activate(activation.id, "SCHEDULER")


def _start_failed(now: timezone.datetime):
    cutoff_time = now - timedelta(
        seconds=settings.ACTIVATION_RESTART_SECONDS_ON_FAILURE
    )
    restart_policies = [
        RestartPolicy.ALWAYS,
        RestartPolicy.ON_FAILURE,
    ]
    for activation in models.Activation.objects.filter(
        is_enabled=True,
        is_valid=True,
        status=ActivationStatus.FAILED,
        restart_policy__in=restart_policies,
        failure_count__lt=settings.ACTIVATION_MAX_RESTARTS_ON_FAILURE,
        status_updated_at__lt=cutoff_time,
    ):
        logger.info(
            f"Restart activation {activation.name} according to its restart"
            " policy."
        )
        activate(activation.id, "SCHEDULER")


def _reconnect_activations() -> list[int]:
    """Reconnect activations monitored by already dead workers to live ones.

    Return list of ids of reconnecting activations
    """
    running_statuses = [
        ActivationStatus.RUNNING,
        ActivationStatus.STARTING,
    ]
    reconnecting_activations = []
    for activation in models.Activation.objects.filter(
        status__in=running_statuses
    ):
        if not _is_worker_alive(activation.worker_name):
            logger.info(
                f"The activation worker for actvation_id {activation.id} is "
                "dead. Will find another worker to reconnect to the instance"
            )
            job_id = _activation_job_id(activation.id)
            job = job_from_queue(get_queue(name="activation"), job_id)
            if job:
                job.cancel()
            activate(
                activation_id=activation.id,
                requester="SCHEDULER",
                reconnect=True,
            )
            reconnecting_activations.append(activation.id)
    return reconnecting_activations


def _is_worker_alive(worker_name: str) -> bool:
    for worker in _get_activation_workers():
        if worker.name == worker_name:
            return (
                worker.get_state() == WorkerStatus.BUSY
                or worker.get_state() == WorkerStatus.IDLE
            )
    return False


def _get_activation_workers() -> list[Worker]:
    return Worker.all(queue=get_queue("activation"))
