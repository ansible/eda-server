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
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django_rq import get_scheduler
from rq.job import JobStatus

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.core.tasking import get_queue, job
from aap_eda.services.ruleset.activate_rulesets import ActivateRulesets
from aap_eda.services.ruleset.activation_db_logger import ActivationDbLogger

logger = logging.getLogger(__name__)


@job("activation")
def activate(activation_id: int, requester: str = "User") -> None:
    logger.info(
        f"Activating activation id: {activation_id} requested "
        f"by {requester}"
    )

    with transaction.atomic():
        activation = (
            models.Activation.objects.select_for_update()
            .filter(id=activation_id)
            .first()
        )
        if (
            not activation
            or str(activation.status) == ActivationStatus.DELETING.value
        ):
            logger.info(f"Activation id: {activation_id} is deleted")
            return

        if not activation.is_enabled:
            logger.info(f"Activation id: {activation_id} is disabled")
            return

        activation.status = ActivationStatus.STARTING
        activation.save(update_fields=["status"])

        # Note: expect scheduler to set requester as "SCHEDULER"
        if requester == "SCHEDULER":
            activation.restart_count += 1
            activation.save(update_fields=["restart_count", "modified_at"])

    ActivateRulesets().activate(activation)

    logger.info(f"Activation {activation.name} is done.")


@job("default")
def deactivate(
    activation_id: int, requester: str = "User", delete: bool = False
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

        if str(activation.status) in [
            ActivationStatus.COMPLETED.value,
            ActivationStatus.FAILED.value,
            ActivationStatus.STOPPED.value,
        ]:
            logger.warning(
                f"Cannot deactivate the activation {activation.name} when its "
                f"status is {activation.status}"
            )
            return

        _perform_deactivate(activation)

        if delete:
            logger.info(f"Activation {activation.name} is deleted")
            activation.delete()
        else:
            activation.current_job_id = None
            activation.status = ActivationStatus.STOPPED
            activation.save()


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

        if str(activation.status) not in [
            ActivationStatus.COMPLETED.value,
            ActivationStatus.FAILED.value,
            ActivationStatus.STOPPED.value,
        ]:
            _perform_deactivate(activation)

        activation.refresh_from_db()
        if str(activation.status) in [
            ActivationStatus.STOPPING.value,
            ActivationStatus.DELETING.value,
        ]:
            logger.warning(
                f"Cannot restart the activation {activation.name} when its "
                f"status is {activation.status}"
            )
            return

        activation.status = ActivationStatus.PENDING
        activation.save(update_fields=["status", "modified_at"])

        activate.delay(activation_id, requester)


def _perform_deactivate(activation: models.Activation) -> None:
    logger.info(f"Task started: Deactivate Activation ({activation.name})")

    # clear the job from rq if it's pending/running
    job_id = activation.current_job_id

    if job_id:
        queue = get_queue(name="activation")
        job = queue.fetch_job(job_id)
        if job and job.get_status(refresh=True) in [
            JobStatus.QUEUED,
            JobStatus.STARTED,
            JobStatus.DEFERRED,
            JobStatus.SCHEDULED,
        ]:
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

        ActivateRulesets().deactivate(instance=instance)


# This is job will be scheduled by a scheduler which currently is unavailable
def monitor_activations() -> None:
    # 1. Set status = unresponsive (all instances):
    #    if status in [running, starting] and updated_at has timeouted
    # 2. Restart (check latest instance):
    #    if status is unresponsive and updated_at has timeouted
    logger.info("Task started: monitor_activations")
    now = datetime.utcnow()
    running_statuses = [
        ActivationStatus.RUNNING.value,
        ActivationStatus.STARTING.value,
    ]
    cutoff_time = now - timedelta(
        seconds=int(settings.RULEBOOK_LIVENESS_TIMEOUT_SECONDS)
    )
    models.ActivationInstance.objects.filter(
        status__in=running_statuses, updated_at__lt=cutoff_time
    ).update(status=ActivationStatus.UNRESPONSIVE.value, updated_at=now)

    # TODO: Temporarily disable the restart logic until a proper worker can
    # pick up the job
    """
    restart_policies = [
        RestartPolicy.ALWAYS.value,
        RestartPolicy.ON_FAILURE.value,
    ]
    for activation in models.Activation.objects.filter(
        is_enabled=True, restart_policy__in=restart_policies
    ):
        instance = (
            models.ActivationInstance.objects.filter(activation=activation)
            .order_by("-started_at")
            .first()
        )
        if (
            instance
            and instance.status == ActivationStatus.UNRESPONSIVE.value
            and now - instance.updated_at
            > timedelta(seconds=int(settings.RULEBOOK_LIVENESS_CHECK_SECONDS))
        ):
            logger.info(f"Now is {now}, updated_at {instance.updated_at}")
            logger.info(
                f"Lost heartbeat for activation {activation.name})."
                " Restart now according to its restart policy."
            )
            activate_rulesets.delay(
                is_restart=True,
                activation_id=activation.id,
                deployment_type=settings.DEPLOYMENT_TYPE,
                ws_base_url=settings.WEBSOCKET_BASE_URL,
                ssl_verify=settings.WEBSOCKET_SSL_VERIFY,
            )
    """


def enqueue_restart_task(seconds: int, activation_id: int) -> None:
    time_at = datetime.utcnow() + timedelta(seconds=seconds)
    logger.info(
        "Enqueueing restart task for activation id: %s, at %s",
        activation_id,
        time_at,
    )
    get_scheduler(name="activation").enqueue_at(
        time_at,
        activate,
        activation_id,
    )
