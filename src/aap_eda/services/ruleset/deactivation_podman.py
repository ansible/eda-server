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

from podman import PodmanClient
from podman.errors.exceptions import APIError

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus

from .activation_db_logger import ActivationDbLogger

logger = logging.getLogger(__name__)


class DeactivationPodman:
    def __init__(
        self,
        podman_url: str,
        activation_db_logger: ActivationDbLogger,
    ) -> None:
        if podman_url:
            self.podman_url = podman_url
        else:
            self._default_podman_url()
        logger.info(f"Using podman socket: {self.podman_url}")

        self.client = PodmanClient(base_url=self.podman_url)
        logger.info(self.client.version())
        self.activation_db_logger = activation_db_logger

    def deactivate(
        self,
        activation_instance: models.ActivationInstance,
    ) -> None:
        container_id = activation_instance.activation_pod_id
        try:
            self.activation_db_logger.write(
                "Activation being stopped at user request", True
            )
            if self.client.containers.exists(container_id):
                container = self.client.containers.get(container_id)
                container.stop(ignore=True)
                container.remove(force=True, v=True)

                message = f"Container {container_id} is removed."
                logger.info(message)
                self.activation_db_logger.write(message, True)
            else:
                logger.warning(f"Container {container_id} not found.")
                self.activation_db_logger.write(
                    f"Container {container_id} not found.", True
                )

            activation_instance.activation_pod_id = None
            activation_instance.status = ActivationStatus.STOPPED
            activation_instance.save(
                update_fields=["status", "activation_pod_id"]
            )
        except APIError as e:
            logger.exception(
                f"Failed to remove container: {container_id}; error: {str(e)}"
            )
            raise

    def _default_podman_url(self) -> None:
        if os.getuid() == 0:
            self.podman_url = "unix:///run/podman/podman.sock"
        else:
            xdg_runtime_dir = os.getenv(
                "XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"
            )
            self.podman_url = f"unix://{xdg_runtime_dir}/podman/podman.sock"
