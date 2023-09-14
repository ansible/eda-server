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
from django.db import DatabaseError
from django.utils import timezone
from podman import PodmanClient
from podman.domain.containers import Container
from podman.domain.images import Image
from podman.errors import ContainerError, ImageNotFound
from podman.errors.exceptions import APIError, NotFound

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus

from .activation_db_logger import ActivationDbLogger
from .exceptions import ActivationException, ActivationRecordNotFound
from .shared_settings import VALID_LOG_LEVELS

logger = logging.getLogger(__name__)

FLUSH_AT_END = -1
GRACEFUL_TERM = 143

CONTAINER_ERROR_CODES_MAP = {
    0: "Normal Stopped",
    1: "Application Error",
    125: "Container Failed to Run",
    126: "Command Invoke Error",
    127: "File or Directory Not Found",
    128: "Invalid Argument Used on Exit",
    134: "Abnormal Termination (SIGABRT)",
    137: "Immediate Termination (SIGKILL)",
    139: "Segmentation Fault (SIGSEGV)",
    143: "Graceful Termination (SIGTERM)",
    255: "Exit Status Out of Range",
}


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
            raise ActivationException(
                f"DecisionEnvironment: {self.decision_environment.name} does"
                " not have image_url set"
            )
        self.pod_args = {}
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
        activation_instance: models.ActivationInstance,
        heartbeat: int,
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
                str(activation_instance.id),
                "--heartbeat",
                str(heartbeat),
            ]
            if (
                settings.ANSIBLE_RULEBOOK_LOG_LEVEL
                and settings.ANSIBLE_RULEBOOK_LOG_LEVEL in VALID_LOG_LEVELS
            ):
                args.append(settings.ANSIBLE_RULEBOOK_LOG_LEVEL)

            self.pod_args[
                "name"
            ] = f"eda-{activation_instance.id}-{uuid.uuid4()}"
            if ports:
                self.pod_args["ports"] = ports
            self._load_extra_args()
            self.activation_db_logger.write("Starting Container", True)
            self.activation_db_logger.write(f"Container args {args}", True)
            container = self.client.containers.run(
                image=self.decision_environment.image_url,
                command=args,
                stdout=True,
                stderr=True,
                remove=True,
                detach=True,
                **self.pod_args,
            )

            logger.info(
                f"Created container: "
                f"name: {container.name}, "
                f"id: {container.id}, "
                f"ports: {container.ports}, "
                f"status: {container.status}, "
                f"command: {args}"
            )

            now = timezone.now()
            activation_instance.status = ActivationStatus.RUNNING
            activation_instance.updated_at = now
            activation_instance.activation_pod_id = container.id
            activation_instance.save(
                update_fields=["status", "updated_at", "activation_pod_id"]
            )

            activation = activation_instance.activation
            activation.status = ActivationStatus.RUNNING
            activation.is_valid = True
            activation.status_updated_at = now
            activation.save(
                update_fields=[
                    "status",
                    "status_updated_at",
                    "is_valid",
                    "modified_at",
                ]
            )

            self._save_logs(container=container, instance=activation_instance)

            if self.return_code == GRACEFUL_TERM:
                activation_instance.status = ActivationStatus.STOPPED
            else:
                activation_instance.status = ActivationStatus.COMPLETED
            activation_instance.save(update_fields={"status"})
        except ActivationException as e:
            logger.error(e)
        except ContainerError:
            logger.exception("Container error")
            raise
        except ImageNotFound:
            logger.exception("Image not found")
            raise
        except APIError:
            logger.exception("Container run failed")
            raise
        except DatabaseError:
            message = (
                f"Activation instance {activation_instance.id} is not present."
            )
            raise ActivationRecordNotFound(message)
        finally:
            if container and self.client.containers.exists(container.id):
                container_id = container.id
                try:
                    container.remove(force=True, v=True)
                    logger.info(f"Container {container_id} is cleaned up.")
                except NotFound:
                    logger.info(f"Container {container_id} not found.")

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
            self.activation_db_logger.write(
                f"Attempting to login to registry: {registry}", True
            )
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
            raise

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
        try:
            credential = self.decision_environment.credential
            self.activation_db_logger.write(
                f"Pulling image {self.decision_environment.image_url}", True
            )
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
            raise

    def _save_logs(
        self, container: Container, instance: models.ActivationInstance
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
            logger.info(f"log stream ended for {container.id}")

        try:
            self.return_code = container.wait(condition="exited")
            logger.info(f"return_code: {self.return_code}")
            self.activation_db_logger.write(
                f"Container exit code: {self.return_code}"
            )

            # If we haven't streamed any lines, collect the logs
            # when the container ends.
            # Seems to be differences between 4.1.1 and 4.5 of podman
            if lines_streamed == 0:
                for line in container.logs():
                    self.activation_db_logger.write(line.decode("utf-8"))

            logger.info(
                f"{self.activation_db_logger.lines_written()}"
                " activation instance log entries created."
            )
        except NotFound:
            self.return_code = GRACEFUL_TERM
            logger.info(f"Container {container.id} was removed.")

        message = CONTAINER_ERROR_CODES_MAP.get(
            self.return_code, f"exit code {self.return_code}"
        )
        if self.return_code == 0 or self.return_code == GRACEFUL_TERM:
            logger.info(f"Container {container.id} received {message}.")
            self.activation_db_logger.write(
                f"Container {container.id} received {message}.", True
            )
        else:
            instance.status = ActivationStatus.FAILED
            instance.save(update_fields=["status"])
            raise ActivationException(f"Activation failed: {message}")

    def _load_extra_args(self) -> None:
        if hasattr(settings, "PODMAN_MEM_LIMIT") and settings.PODMAN_MEM_LIMIT:
            self.pod_args["mem_limit"] = settings.PODMAN_MEM_LIMIT

        if hasattr(settings, "PODMAN_MOUNTS") and settings.PODMAN_MOUNTS:
            self.pod_args["mounts"] = settings.PODMAN_MOUNTS

        if hasattr(settings, "PODMAN_ENV_VARS") and settings.PODMAN_ENV_VARS:
            self.pod_args["environment"] = settings.PODMAN_ENV_VARS

        if (
            hasattr(settings, "PODMAN_EXTRA_ARGS")
            and settings.PODMAN_EXTRA_ARGS
        ):
            for key, value in settings.PODMAN_EXTRA_ARGS.items():
                self.pod_args[key] = value

        for key, value in self.pod_args.items():
            logger.debug("Key %s Value %s", key, value)
