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

from django.db import transaction

from aap_eda import tasks

from .ansible_rulebook_command import ansible_rulebook_command

__all__ = (
    "activate_rulesets",
    "deactivate_rulesets",
)

logger = logging.getLogger(__name__)


class DeploymentType(Enum):
    LOCAL = "local"
    DOCKER = "docker"
    PODMAN = "podman"
    K8S = "k8s"


@transaction.atomic
def activate_rulesets(
    deployment_type: str,
    activation_id: int,
    large_data_id: int,
    execution_environment: str,
    rulesets: str,
    inventory: str,
    extravars: str,
    working_directory: str,
    host: str,
    port: int,
) -> None:

    local_working_directory = working_directory
    ensure_directory(local_working_directory)

    logger.debug("activate_rulesets %s %s", activation_id, deployment_type)

    if deployment_type == DeploymentType.LOCAL.value:
        cmd_args = [
            "--worker",
            "--websocket-address",
            "ws://localhost:8000/api/eda/ws2",
            "--id",
            str(activation_id),
            "--debug",
        ]

        result = ansible_rulebook_command(
            cmd_args,
            cwd=local_working_directory,
        )
        logger.info(result)
        tasks.read_output(result, activation_id)

    # TODO: implement this later
    elif deployment_type == "docker" or deployment_type == "podman":
        pass
    elif deployment_type == "k8s":
        logger.error("k8s deployment not implemented yet")
    else:
        raise Exception("Unsupported deployment_type")


@transaction.atomic
def deactivate_rulesets():
    pass


# Utility functions
# -------------------------------------------------------------


def ensure_directory(directory):
    if os.path.exists(directory):
        return directory
    else:
        os.makedirs(directory)
        return directory
