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

import base64
import json
import logging
import os
import uuid

from django.conf import settings
from podman import PodmanClient
from podman.domain.containers import Container
from podman.domain.images import Image
from podman.errors import ContainerError, ImageNotFound
from podman.errors.exceptions import APIError

from aap_eda.core import models

from .activation_db_logger import ActivationDbLogger
from .exceptions import ActivationValidationError, PodmanActivationException
from .shared_settings import VALID_LOG_LEVELS

logger = logging.getLogger(__name__)

FLUSH_AT_END = -1


class ActivationPodman:
    def __init__(
        self,
        decision_environment: models.DecisionEnvironment,
        podman_url: str,
        activation_db_logger: ActivationDbLogger,
    ) -> None:
        self.decision_environment = decision_environment
        self.activation_db_logger = activation_db_logger

        if not self.decision_environment.image_url:
            raise ActivationValidationError(
                f"DecisionEnvironment: {self.decision_environment.name} does"
                " not have image_url set"
            )

        if podman_url:
            self.podman_url = podman_url
        else:
            self._default_podman_url()
        logger.info(f"Using podman socket: {self.podman_url}")

        self._set_auth_json_file()

        self.client = PodmanClient(base_url=self.podman_url)
        self._login()

        self.image = self._pull_image()
        logger.info(self.client.version())

    def run_worker_mode(
        self,
        ws_url: str,
        ws_ssl_verify: str,
        activation_instance_id: str,
        heartbeat: str,
        ports: dict,
    ) -> None:
        container = None
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
                "--heartbeat",
                str(heartbeat),
            ]
            if (
                settings.ANSIBLE_RULEBOOK_LOG_LEVEL
                and settings.ANSIBLE_RULEBOOK_LOG_LEVEL in VALID_LOG_LEVELS
            ):
                args.append(settings.ANSIBLE_RULEBOOK_LOG_LEVEL)

            container = self.client.containers.run(
                image=self.decision_environment.image_url,
                command=args,
                stdout=True,
                stderr=True,
                remove=True,
                detach=True,
                name=f"eda-{activation_instance_id}-{uuid.uuid4()}",
                ports=ports,
            )

            logger.info(
                f"Created container: "
                f"name: {container.name}, "
                f"ports: {container.ports}, "
                f"status: {container.status}, "
                f"command: {args}"
            )

            self._save_logs(
                container=container,
                activation_instance_id=activation_instance_id,
            )

        except ContainerError:
            logger.exception("Container error")
            raise PodmanActivationException("Container error")
        except ImageNotFound:
            logger.exception("Image not found")
            raise PodmanActivationException("Image not found")
        except APIError:
            logger.exception("Container run failed")
            raise PodmanActivationException("Container run failed")
        finally:
            if container:
                container.remove()

    def _default_podman_url(self) -> None:
        if os.getuid() == 0:
            self.podman_url = "unix:///run/podman/podman.sock"
        else:
            xdg_runtime_dir = os.getenv(
                "XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"
            )
            self.podman_url = f"unix://{xdg_runtime_dir}/podman/podman.sock"

    def _login(self) -> None:
        credential = self.decision_environment.credential
        if not credential:
            return

        try:
            registry = self.decision_environment.image_url.split("/")[0]
            self.client.login(
                username=credential.username,
                password=credential.secret.get_secret_value(),
                registry=registry,
            )

            logger.debug(
                f"{credential.username} login succeeded to {registry}"
            )
        except APIError:
            logger.exception("Login failed")
            raise PodmanActivationException("Login failed")

    def _write_auth_json(self) -> None:
        if not self.auth_file:
            logger.debug("No auth file to create")
            return

        auth_dict = {}
        if os.path.exists(self.auth_file):
            with open(self.auth_file) as f:
                auth_dict = json.load(f)

        if "auths" not in auth_dict:
            auth_dict["auths"] = {}

        registry = self.decision_environment.image_url.split("/")[0]
        auth_dict["auths"][registry] = self._create_auth_key()

        with open(self.auth_file, "w") as f:
            json.dump(auth_dict, f, indent=6)

    def _create_auth_key(self) -> dict:
        cred = self.decision_environment.credential
        data = f"{cred.username}:{cred.secret.get_secret_value()}"
        encoded_data = data.encode("ascii")
        return {"auth": base64.b64encode(encoded_data).decode("ascii")}

    def _set_auth_json_file(self) -> None:
        xdg_runtime_dir = os.getenv(
            "XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"
        )
        auth_file = f"{xdg_runtime_dir}/containers/auth.json"
        dir_name = os.path.dirname(auth_file)
        if os.path.exists(dir_name):
            self.auth_file = auth_file
            logger.debug("Will use auth file %s", auth_file)
        else:
            self.auth_file = None
            logger.debug("Will not use auth file")

    def _pull_image(self) -> Image:
        credential = self.decision_environment.credential
        try:
            kwargs = {}
            if credential:
                kwargs["auth_config"] = {
                    "username": credential.username,
                    "password": credential.secret.get_secret_value(),
                }
                self._write_auth_json()
            return self.client.images.pull(
                self.decision_environment.image_url, **kwargs
            )
        except ImageNotFound:
            logger.exception(
                f"Image {self.decision_environment.image_url} not found"
            )
            raise PodmanActivationException("Image not found")

    def _save_logs(
        self, container: Container, activation_instance_id: str
    ) -> None:
        lines_streamed = 0
        dkg = container.logs(
            stream=True, follow=True, stderr=True, stdout=True
        )
        try:
            while True:
                line = next(dkg).decode("utf-8")
                self.activation_db_logger.write(line)
                lines_streamed += 1
        except StopIteration:
            logger.info(f"log stream ended for {container.name}")

        self.return_code = container.wait(condition="exited")
        logger.info(f"return_code: {self.return_code}")

        # If we haven't streamed any lines, collect the logs
        # when the container ends.
        # Seems to be differences between 4.1.1 and 4.5 of podman
        if lines_streamed == 0:
            for line in container.logs():
                self.activation_db_logger.write(line.decode("utf-8"))

        self.activation_db_logger.write(
            f"Container exit code: {self.return_code}"
        )
        logger.info(
            f"{self.activation_db_logger.lines_written()}"
            " activation instance log entries created."
        )

        if self.return_code > 0:
            raise PodmanActivationException(
                f"Activation failed in {container.name}"
            )
