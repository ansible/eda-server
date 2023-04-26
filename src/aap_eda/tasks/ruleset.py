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
from django.utils import timezone

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus, RestartPolicy
from aap_eda.core.tasking import get_queue, job
from aap_eda.services.ruleset.activate_rulesets import ActivateRulesets

logger = logging.getLogger(__name__)


@job
def activate_rulesets(
    activation_id: int,
    decision_environment_id: int,
    deployment_type: str,
    ws_base_url: str,
    ssl_verify: str,
) -> None:
    logger.info(f"Task started: Activate rulesets ({activation_id=})")

    instance = ActivateRulesets().activate(
        activation_id,
        decision_environment_id,
        deployment_type,
        ws_base_url,
        ssl_verify,
    )

    if instance.status == ActivationStatus.COMPLETED.value and (
        instance.activation.restart_policy == RestartPolicy.ALWAYS.value
    ):
        logger.info(
            f"Task finished: Rulesets ({activation_id=}) are activated."
            " State is being monitored."
        )
        enqueue_monitor_task(
            activation_id,
            decision_environment_id,
            deployment_type,
            ws_base_url,
            ssl_verify,
        )
    else:
        logger.info(
            f"Task finished: Rulesets ({activation_id=}) {instance.status=}."
        )


@job
def monitor_and_restart_activation(
    activation_id: int,
    decision_environment_id: int,
    deployment_type: str,
    ws_base_url: str,
    ssl_verify: str,
) -> None:
    logger.info(f"Task started: Monitor activation ({activation_id=})")

    activation = models.Activation.objects.get(pk=activation_id)
    if not activation.is_enabled:
        return

    activation_instances = models.ActivationInstance.objects.filter(
        activation_id=activation.id
    )

    restart = False
    if activation_instances:
        instance = activation_instances.latest("started_at")
        if instance.status == ActivationStatus.FAILED.value and (
            activation.restart_policy == RestartPolicy.ALWAYS.value
            or activation.restart_policy == RestartPolicy.ON_FAILURE.value
        ):
            logger.info(f"Activation ({activation_id=}) failed. Restart now.")
            restart = True
        elif (
            instance.status == ActivationStatus.COMPLETED.value
            and activation.restart_policy == RestartPolicy.ALWAYS.value
        ):
            if timezone.now() - instance.updated_at > timedelta(
                seconds=int(settings.RULEBOOK_LIVENESS_TIMEOUT_SECONDS)
            ):
                logger.info(
                    f"Lost heartbeat for Rulebook ({activation_id=})."
                    " Restart now."
                )
                restart = True
            else:
                logger.info(
                    f"Rulesets ({activation_id=}) in good state."
                    " Keep on monitoring."
                )
                enqueue_monitor_task(
                    activation_id,
                    decision_environment_id,
                    deployment_type,
                    ws_base_url,
                    ssl_verify,
                )

    if restart:
        activate_rulesets(
            activation_id,
            decision_environment_id,
            deployment_type,
            ws_base_url,
            ssl_verify,
        )


def enqueue_monitor_task(
    activation_id: int,
    decision_environment_id: int,
    deployment_type: str,
    ws_base_url: str,
    ssl_verify: str,
) -> None:
    queue = get_queue()
    time_at = timezone.now() + timedelta(
        seconds=int(settings.RULEBOOK_LIVENESS_CHECK_SECONDS)
    )
    queue.enqueue_at(
        time_at,
        monitor_and_restart_activation,
        args=(
            activation_id,
            decision_environment_id,
            deployment_type,
            ws_base_url,
            ssl_verify,
        ),
    )
