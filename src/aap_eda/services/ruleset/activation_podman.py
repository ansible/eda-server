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
from podman.errors import ContainerError, ImageNotFound

from .exceptions import ActivationException

logger = logging.getLogger(__name__)


class ActivationPodman:
    def __init__(self, image_name: str, podman_url: str):
        if podman_url:
            self.podman_url = podman_url
        else:
            self._default_podman_url()
        logger.info(self.podman_url)

        self.client = PodmanClient(base_url=self.podman_url)
        self.image = self.client.images.pull(image_name)
        logger.info(self.client.version())

    def run_worker_mode(
        self,
        ws_url: str,
        ws_ssl_verify: str,
        activation_instance_id: str,
    ):
        try:
            """Run ansible-rulebook in worker mode."""
            args = [
                "ansible-rulebook",
                "--worker",
                "--websocket-ssl-verify",
                ws_ssl_verify,
                "--websocket-address",
                ws_url,
                "--id",
                str(activation_instance_id),
            ]

            container = self.client.containers.run(
                image=self.image,
                command=args,
                stdout=True,
                stderr=True,
                remove=True,
                detach=True,
            )

            container.wait(condition="exited")

            logger.info(
                f"Created container: name: {container.name}, "
                f"status: {container.status}, "
                f"command: {args}"
            )

            return container
        except ContainerError:
            logger.exception("Container error")
            raise ActivationException("Container error")
        except ImageNotFound:
            logger.exception("Image not found")
            raise ActivationException("Image not found")

    def _default_podman_url(self):
        if os.getuid() == 0:
            self.podman_url = "unix:///run/podman/podman.sock"
        else:
            xdg_runtime_dir = os.getenv(
                "XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"
            )
            self.podman_url = f"unix://{xdg_runtime_dir}/podman/podman.sock"
