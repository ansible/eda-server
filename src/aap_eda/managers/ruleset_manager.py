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

from aap_eda.core.types import StrPath
from aap_eda.tasks.ruleset import activate_rulesets

logger = logging.getLogger(__name__)
LOCAL_WS_ADDRESS = "ws://localhost:8000/api/eda/ws/ansible-rulebook"


class DeploymentType(Enum):
    LOCAL = "local"
    DOCKER = "docker"
    PODMAN = "podman"
    K8S = "k8s"


class RulesetManager:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
    ):
        self.host = host
        self.port = port

    def activate(
        self,
        activation_instance_id: str,
        execution_environment: str,
        working_directory: StrPath,
        deployment_type: DeploymentType = DeploymentType.LOCAL,
    ):
        os.makedirs(working_directory, exist_ok=True)

        if deployment_type == DeploymentType.LOCAL:
            activate_rulesets(LOCAL_WS_ADDRESS, activation_instance_id)
        elif (
            deployment_type == DeploymentType.PODMAN
            or deployment_type == DeploymentType.DOCKER
        ):
            pass
        elif deployment_type == DeploymentType.K8S:
            logger.error(f"{deployment_type} is not implemented yet")
        else:
            raise Exception(f"Unsupported {deployment_type}")
