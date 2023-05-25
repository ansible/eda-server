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
import importlib.metadata
import json
import logging
import os
import re
import uuid
from typing import Iterator, Union

import podman.api
from django.conf import settings
from podman import PodmanClient
from podman.domain.containers import Container
from podman.domain.images import Image
from podman.errors import ContainerError, ImageNotFound
from podman.errors.exceptions import APIError

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus

from .activation_db_logger import ActivationDbLogger
from .exceptions import ActivationException
from .shared_settings import VALID_LOG_LEVELS

logger = logging.getLogger(__name__)

FLUSH_AT_END = -1

PODMAN_VERSION = importlib.metadata.version("podman")


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

            self.pod_args[
                "name"
            ] = f"eda-{activation_instance_id}-{uuid.uuid4()}"
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
                f"ports: {container.ports}, "
                f"status: {container.status}, "
                f"command: {args}"
            )

            self.set_activation_status(
                activation_instance_id, ActivationStatus.RUNNING
            )
            self._save_logs(
                container=container,
                activation_instance_id=activation_instance_id,
            )

        except ContainerError:
            logger.exception("Container error")
            raise
        except ImageNotFound:
            logger.exception("Image not found")
            raise
        except APIError:
            logger.exception("Container run failed")
            raise
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
        credential = self.decision_environment.credential
        self.activation_db_logger.write(
            f"Pulling image {self.decision_environment.image_url}", True
        )
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
            raise

    def _save_logs(
        self, container: Container, activation_instance_id: str
    ) -> None:
        dkg = _container_logs(
            container, stream=True, follow=True, stderr=True, stdout=True
        )
        try:
            while True:
                line = next(dkg).decode("utf-8")
                self.activation_db_logger.write(line)
        except StopIteration:
            logger.info(f"log stream ended for {container.name}")

        self.return_code = container.wait(condition="exited")
        logger.info(f"return_code: {self.return_code}")

        self.activation_db_logger.write(
            f"Container exit code: {self.return_code}"
        )
        logger.info(
            f"{self.activation_db_logger.lines_written()}"
            " activation instance log entries created."
        )

        if self.return_code > 0:
            raise ActivationException(f"Activation failed in {container.name}")

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

    def set_activation_status(
        self, activation_instance_id: int, status: ActivationStatus
    ) -> None:
        instance = models.ActivationInstance.objects.get(
            id=activation_instance_id
        )
        if not instance:
            raise ActivationException(
                f"Activation instance {activation_instance_id} " "not found"
            )
        instance.status = status
        instance.save()


def _container_logs(container, **kwargs) -> Union[bytes, Iterator[bytes]]:
    """
    Backport of podman container logs function.

    This function includes patch for log streaming issue to be used with
    versions of podman-py prior to 4.2.
    """
    # NOTE(cutwater): This is a dirty hack to compare podman version without
    #   third party dependencies. While the distribution version is available
    #   by calling the `importlib.metadata.version` function
    #   or via the `podman.__version__` attribute, both versions are strings.
    #   The Python standard library doesn't provide a mechanism to parse and
    #   appropriately compare PEP440 versions. This is implemented in the
    #   standalone `packaging` distribution, which is not available
    #   in the project's main dependency list.
    if not re.match(r"3|4\.[01]", PODMAN_VERSION):
        return container.logs(**kwargs)

    stream = bool(kwargs.get("stream", False))
    params = {
        "follow": kwargs.get("follow", kwargs.get("stream", None)),
        "since": podman.api.prepare_timestamp(kwargs.get("since")),
        "stderr": kwargs.get("stderr", None),
        "stdout": kwargs.get("stdout", True),
        "tail": kwargs.get("tail"),
        "timestamps": kwargs.get("timestamps"),
        "until": podman.api.prepare_timestamp(kwargs.get("until")),
    }

    response = container.client.get(
        f"/containers/{container.id}/logs", stream=stream, params=params
    )
    response.raise_for_status()

    if stream:
        return podman.api.stream_frames(response)
    return podman.api.frames(response)
