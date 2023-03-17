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
import os
from enum import Enum
from typing import Optional

from django.utils import timezone

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.core.types import StrPath

from .ansible_rulebook import AnsibleRulebookService

logger = logging.getLogger(__name__)
LOCAL_WS_ADDRESS = "ws://{host}:{port}/api/eda/ws/ansible-rulebook"


class ActivateRulesetsFailed(Exception):
    pass


class DeploymentType(Enum):
    LOCAL = "local"
    DOCKER = "docker"
    PODMAN = "podman"
    K8S = "k8s"


class ActivateRulesets:
    def __init__(self, cwd: Optional[str] = None):
        self.service = AnsibleRulebookService(cwd)

    def activate(
        self,
        activation_id: int,
        execution_environment: str,
        working_directory: StrPath,
        deployment_type: str,
        host: str,
        port: int,
    ):
        try:
            instance = models.ActivationInstance.objects.create(
                activation_id=activation_id
            )
            instance.status = ActivationStatus.RUNNING

            os.makedirs(working_directory, exist_ok=True)

            dtype = DeploymentType(deployment_type)

            if dtype == DeploymentType.LOCAL:
                self.activate_in_local(LOCAL_WS_ADDRESS.format(host=host, port=port), instance.id)
            elif (
                dtype == DeploymentType.PODMAN
                or dtype == DeploymentType.DOCKER
            ):
                self.activate_in_docker_podman()
            elif dtype == DeploymentType.K8S:
                logger.error(f"{deployment_type} is not implemented yet")
            else:
                raise ActivateRulesetsFailed(f"Unsupported {deployment_type}")

            instance.status = ActivationStatus.COMPLETED
        except Exception as exe:
            logger.error(f"Activation error: {str(exe)}")
            instance.status = ActivationStatus.FAILED
        finally:
            instance.ended_at = timezone.now()
            instance.save()

    def activate_in_local(
        self,
        url: str,
        activation_instance_id: str,
    ) -> None:
        proc = self.service.run_worker_mode(url, activation_instance_id)

        line_number = 0

        activation_instance_logs = []
        for line in proc.stdout.splitlines():
            activation_instance_log = models.ActivationInstanceLog(
                line_number=line_number,
                log=line,
                activation_instance_id=int(activation_instance_id),
            )
            activation_instance_logs.append(activation_instance_log)

            line_number += 1

        models.ActivationInstanceLog.objects.bulk_create(
            activation_instance_logs
        )
        logger.info(f"{line_number} of activation instance log are created.")

    # TODO(hsong) implement later
    def activate_in_docker_podman():
        pass
