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

from .activate_rulesets import DeploymentType
from .deactivation_podman import DeactivationPodman
from .exceptions import ActivationException

logger = logging.getLogger(__name__)


class DeactivateRulesets:
    def __init__(self, instance_id: int, deployment_type: str):
        try:
            self.deployment_type = DeploymentType(deployment_type)
        except ValueError:
            raise ActivationException(
                f"Invalid deployment type: {deployment_type}"
            )

        self.instance = models.ActivationInstance.objects.get(id=instance_id)

    def run(self) -> None:
        # TODO: self.instance.status = ActivationStatus.STOPPING
        self.instance.save()

        deactivate = get_deactivate(self.deployment_type)
        deactivate(self.instance)


def get_deactivate(deployment_type: DeploymentType):
    if deployment_type == DeploymentType.LOCAL:
        return local_deactivate
    elif deployment_type == DeploymentType.PODMAN:
        return podman_deactivate
    elif deployment_type == DeploymentType.K8S:
        return k8s_deactivate
    else:
        return docker_deactivate


def local_deactivate(instance: models.ActivationInstance) -> None:
    pass


def podman_deactivate(instance: models.ActivationInstance) -> None:
    if instance.activation_pod_id is None:
        logger.warning(f"Instance {instance.name} does not have container id")
        return

    client = DeactivationPodman(settings.PODMAN_SOCKET_URL)
    client.deactivate(instance)


def docker_deactivate(instance: models.ActivationInstance) -> None:
    pass


def k8s_deactivate(instance: models.ActivationInstance) -> None:
    pass
