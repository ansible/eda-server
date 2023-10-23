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
from datetime import datetime

from django.conf import settings
from podman import PodmanClient
from podman.domain.images import Image
from podman.errors import ContainerError, ImageNotFound
from podman.errors.exceptions import APIError, NotFound

from aap_eda.core.enums import ActivationStatus

from . import exceptions
from .common import ContainerEngine, ContainerRequest, LogHandler

LOGGER = logging.getLogger(__name__)


def get_podman_client():
    """Podman client factory."""
    podman_url = settings.PODMAN_SOCKET_URL
    if podman_url:
        return PodmanClient(base_url=podman_url)

    if os.getuid() == 0:
        podman_url = "unix:///run/podman/podman.sock"
    else:
        xdg_runtime_dir = os.getenv(
            "XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"
        )
        podman_url = f"unix://{xdg_runtime_dir}/podman/podman.sock"
    LOGGER.info(f"Using podman socket: {podman_url}")
    return PodmanClient(base_url=podman_url)


class Engine(ContainerEngine):
    def __init__(
        self,
        _activation_id: str,
        client=None,
    ) -> None:
        if client:
            self.client = client
        else:
            self.client = get_podman_client()
        LOGGER.debug(self.client.version())

    def cleanup(self, container_id: str, log_handler: LogHandler) -> None:
        if self.client.containers.exists(container_id):
            container = self.client.containers.get(container_id)
            container.stop(ignore=True)
            self.update_logs(container_id, log_handler)
            try:
                self._cleanup(container_id, log_handler)
            except APIError as e:
                LOGGER.exception(f"Failed to cleanup container {container_id}")
                raise exceptions.ContainerCleanupError(
                    f"Failed to cleanup container {container_id}"
                ) from e

    def start(self, request: ContainerRequest, log_handler: LogHandler) -> str:
        if not request.image_url:
            raise exceptions.ContainerStartError("Missing image url")

        try:
            self._set_auth_json_file()
            self._login(request)
            LOGGER.info(f"Image URL is {request.image_url}")
            self._pull_image(request, log_handler)
            log_handler.write("Starting Container", True)
            command = request.cmdline.command_and_args()
            log_handler.write(f"Container args {command}", True)
            pod_args = self._load_pod_args(request)
            LOGGER.info(
                "Creating container: "
                f"command: {command}, "
                f"pod_args: {pod_args}"
            )
            container = self.client.containers.run(
                image=request.image_url,
                command=command,
                stdout=True,
                stderr=True,
                remove=True,
                detach=True,
                **pod_args,
            )

            LOGGER.info(
                f"Created container: "
                f"name: {container.name}, "
                f"id: {container.id}, "
                f"ports: {container.ports}, "
                f"status: {container.status}, "
                f"command: {command}, "
                f"pod_args: {pod_args}"
            )

            return str(container.id)
        except (
            ContainerError,
            ImageNotFound,
            APIError,
        ) as e:
            error_message = f"Container Start Error: {e}"
            LOGGER.error(error_message)
            log_handler.write(error_message, flush=True)
            raise exceptions.ContainerStartError(error_message) from e

    # note(alex): the signature of this method is different from the interface
    def get_status(self, container_id: str) -> ActivationStatus:
        if self.client.containers.exists(container_id):
            container = self.client.containers.get(container_id)
            if container.status == "exited":
                exit_code = container.attrs.get("State").get("ExitCode")
                if exit_code == 0:
                    return ActivationStatus.COMPLETED
                else:
                    return ActivationStatus.FAILED
            elif container.status == "running":
                return ActivationStatus.RUNNING
        else:
            raise exceptions.ContainerNotFoundError(
                f"Container id {container_id} not found"
            )

    def update_logs(self, container_id: str, log_handler: LogHandler) -> None:
        try:
            if log_handler.get_log_read_at():
                since = int(log_handler.get_log_read_at().timestamp()) + 1
            else:
                start_dt = "2000-01-01T00:00:00-00:00"
                since = (
                    int(
                        datetime.strptime(
                            start_dt, "%Y-%m-%dT%H:%M:%S%z"
                        ).timestamp()
                    )
                    + 1
                )

            if self.client.containers.exists(container_id):
                # ["running", "stopped", "exited", "unknown"]:
                container = self.client.containers.get(container_id)
                if container.status in ["running", "exited", "stopped"]:
                    log_args = {"timestamps": True, "since": since}
                    dt = None
                    for log in container.logs(**log_args):
                        log = log.decode("utf-8")
                        dt = log.split()[0]
                        log_handler.write(log)

                    if dt:
                        since = datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S%z")

                        log_handler.flush()
                        log_handler.set_log_read_at(since)
            else:
                LOGGER.warning(f"Container {container_id} not found.")
                log_handler.write(f"Container {container_id} not found.", True)
        except APIError as e:
            msg = (
                "Failed to fetch container logs: "
                "{container_id}; error: {str(e)}"
            )
            LOGGER.exception(msg)
            raise exceptions.ContainerUpdateLogsError(msg) from e

    def _cleanup(self, container_id: str, _log_handler: LogHandler):
        if self.client.containers.exists(container_id):
            container = self.client.containers.get(container_id)
            try:
                container.remove(force=True, v=True)
                LOGGER.info(f"Container {container_id} is cleaned up.")
            except NotFound:
                LOGGER.info(f"Container {container_id} not found.")

    def _get_ports(self, found_ports: dict) -> dict:
        ports = {}
        for _, port in found_ports:
            ports[f"{port}/tcp"] = port

        return ports

    def _login(self, request) -> None:
        credential = request.credential
        if not credential:
            return

        try:
            registry = request.image_url.split("/")[0]
            self.client.login(
                username=credential.username,
                password=credential.secret,
                registry=registry,
            )

            LOGGER.debug(
                f"{credential.username} login succeeded to {registry}"
            )
        except APIError:
            LOGGER.exception("Login failed")
            raise

    def _write_auth_json(self, request) -> None:
        if not self.auth_file:
            LOGGER.debug("No auth file to create")
            return

        auth_dict = {}
        if os.path.exists(self.auth_file):
            with open(self.auth_file) as f:
                auth_dict = json.load(f)

        if "auths" not in auth_dict:
            auth_dict["auths"] = {}
        registry = request.image_url.split("/")[0]
        auth_dict["auths"][registry] = self._create_auth_key(
            request.credential
        )

        with open(self.auth_file, "w") as f:
            json.dump(auth_dict, f, indent=6)

    def _create_auth_key(self, credential) -> dict:
        data = f"{credential.username}:{credential.secret}"
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
            LOGGER.debug("Will use auth file %s", auth_file)
        else:
            self.auth_file = None
            LOGGER.debug("Will not use auth file")

    def _pull_image(
        self, request: ContainerRequest, log_handler: LogHandler
    ) -> Image:
        try:
            log_handler.write(f"Pulling image {request.image_url}", True)
            LOGGER.info(f"Pulling image : {request.image_url}")
            kwargs = {}
            if request.credential:
                kwargs["auth_config"] = {
                    "username": request.credential.username,
                    "password": request.credential.secret,
                }
                self._write_auth_json(request)
            image = self.client.images.pull(request.image_url, **kwargs)

            # https://github.com/containers/podman-py/issues/301
            if not image.id:
                msg = (
                    f"Image {request.image_url} pull failed. The image url "
                    "or the credentials may be incorrect."
                )
                LOGGER.error(msg)
                raise exceptions.ContainerImagePullError(msg)
            LOGGER.info("Downloaded image")
            return image
        except ImageNotFound:
            LOGGER.exception(f"Image {request.image_url} not found")
            raise

    def _load_pod_args(self, request) -> dict:
        pod_args = {"name": request.name}
        if request.ports:
            pod_args["ports"] = self._get_ports(request.ports)

        if request.mem_limit:
            pod_args["mem_limit"] = request.mem_limit

        if request.mounts:
            pod_args["mounts"] = request.mounts

        if request.env_vars:
            pod_args["environment"] = request.env_vars

        if request.extra_args:
            for key, value in request.extra_args.items():
                pod_args[key] = value

        for key, value in pod_args.items():
            LOGGER.debug("Key %s Value %s", key, value)

        LOGGER.info(pod_args)
        return pod_args
