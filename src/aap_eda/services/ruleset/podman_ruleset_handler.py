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

from django.conf import settings

from aap_eda.core import models

from .activation_db_logger import ActivationDbLogger
from .activation_podman import ActivationPodman
from .deactivation_podman import DeactivationPodman
from .ruleset_handler import RulesetHandler

logger = logging.getLogger(__name__)


class PodmanRulesetHandler(RulesetHandler):
    def activate(
        self,
        instance: models.ActivationInstance,
        activation_db_logger: ActivationDbLogger,
    ) -> models.ActivationInstance:
        podman = ActivationPodman(
            instance.activation.decision_environment,
            settings.PODMAN_SOCKET_URL,
            activation_db_logger,
        )

        ports = {}
        for _, port in super().find_ports(
            instance.activation.rulebook_rulesets
        ):
            ports[f"{port}/tcp"] = port

        podman.run_worker_mode(
            activation_instance=instance,
            heartbeat=settings.RULEBOOK_LIVENESS_CHECK_SECONDS,
            ports=ports,
        )

    def deactivate(
        self,
        instance: models.ActivationInstance,
        activation_db_logger: ActivationDbLogger,
    ):
        if instance.activation_pod_id is None:
            return

        podman = DeactivationPodman(
            settings.PODMAN_SOCKET_URL, activation_db_logger
        )
        podman.deactivate(instance)
