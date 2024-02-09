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


import typing as tp
from abc import ABC, abstractmethod
from datetime import datetime

from django.conf import settings
from pydantic import BaseModel, validator

import aap_eda.services.activation.engine.exceptions as exceptions
from aap_eda.core.enums import ActivationStatus
from aap_eda.core.models.credential import Credential

from .ports import find_ports


class ContainerableMixinError(Exception):
    """Base class for exceptions from implementers of ContainerableMixin."""

    pass


class ContainerableInvalidError(Exception):
    pass


class ContainerableMixin:
    def get_command_line_parameters(self) -> dict[str, tp.Any]:
        """Return parameters for running ansible-rulebook."""
        return {}

    def get_container_parameters(self) -> dict[str, tp.Any]:
        """Return parameters used to create a ContainerRquest."""
        return {
            "credential": self.get_image_credential(),
            "name": self._get_name(),
            "image_url": self._get_image_url(),
            "ports": self._get_ports(),
            "env_vars": settings.PODMAN_ENV_VARS,
            "extra_args": settings.PODMAN_EXTRA_ARGS,
            "mem_limit": settings.PODMAN_MEM_LIMIT,
            "mounts": settings.PODMAN_MOUNTS,
        }

    def get_image_credential(self) -> tp.Optional[Credential]:
        """Return a decrypted Credential or None for the implementer."""
        credential = self._get_image_credential()
        if credential:
            return Credential(
                username=credential.username,
                secret=credential.secret.get_secret_value(),
            )
        return None

    @abstractmethod
    def get_restart_policy(self) -> str:
        """Return the restart policy for the implementer."""
        ...

    def validate(self):
        """Validate the the implementer is appropriate to be containerized.

        By default no implementer is considered valid.
        """
        raise ContainerableInvalidError("invalid as a containerable")

    @abstractmethod
    def _get_context(self) -> dict[str, tp.Any]:
        """Return the context dictionary used to create a ContainerRquest."""
        ...

    @abstractmethod
    def _get_image_credential(self) -> tp.Optional[Credential]:
        ...

    @abstractmethod
    def _get_image_url(self) -> str:
        ...

    @abstractmethod
    def _get_name(self) -> str:
        """Return the name to use for the ContainerRequest."""
        ...

    def _get_ports(self) -> list[tuple]:
        return find_ports(self._get_rulebook_rulesets(), self._get_context())

    @abstractmethod
    def _get_rulebook_rulesets(self) -> str:
        ...


class LogHandler(ABC):
    @abstractmethod
    def write(
        self,
        lines: tp.Union[list[str], str],
        flush: bool = False,
        timestamp: bool = True,
    ) -> None:
        pass

    @abstractmethod
    def get_log_read_at(self) -> tp.Optional[datetime]:
        pass

    @abstractmethod
    def set_log_read_at(self, dt: datetime):
        pass

    @abstractmethod
    def flush(self) -> None:
        pass


class AnsibleRulebookCmdLine(BaseModel):
    ws_url: str
    ws_ssl_verify: str
    ws_access_token: str
    ws_refresh_token: str
    ws_token_url: str
    heartbeat: int
    id: tp.Union[str, int]  # casted to str
    log_level: tp.Optional[str] = None  # -v or -vv or None

    @validator("id", pre=True)
    def cast_to_str(cls, v):
        return str(v)

    def command(self) -> str:
        return "ansible-rulebook"

    def get_args(self, sanitized=False) -> list[str]:
        args = [
            "--worker",
            "--websocket-ssl-verify",
            self.ws_ssl_verify,
            "--websocket-url",
            self.ws_url,
            "--websocket-access-token",
            "******" if sanitized else self.ws_access_token,
            "--websocket-refresh-token",
            "******" if sanitized else self.ws_refresh_token,
            "--websocket-token-url",
            self.ws_token_url,
            "--id",
            self.id,
            "--heartbeat",
            str(self.heartbeat),
        ]
        if self.log_level:
            args.append(self.log_level)

        return args

    def command_and_args(self, sanitized=False) -> list[str]:
        args = self.get_args(sanitized)
        args.insert(0, self.command())
        return args


class Credential(BaseModel):
    username: str
    secret: str


class ContainerRequest(BaseModel):
    name: str  # f"eda-{activation_instance.id}-{uuid.uuid4()}"
    image_url: str  # quay.io/ansible/ansible-rulebook:main
    cmdline: AnsibleRulebookCmdLine
    activation_instance_id: str
    activation_id: str
    credential: tp.Optional[Credential] = None
    ports: tp.Optional[list[tuple]] = None
    pull_policy: str = settings.DEFAULT_PULL_POLICY  # Always by default
    mem_limit: tp.Optional[str] = None
    mounts: tp.Optional[list[dict]] = None
    env_vars: tp.Optional[dict] = None
    extra_args: tp.Optional[dict] = None


class ContainerStatus(BaseModel):
    status: ActivationStatus
    message: str = ""


class ContainerEngine(ABC):
    """Abstract interface to connect to the deployment backend."""

    @abstractmethod
    def __init__(self, activation_id: str):
        ...

    @abstractmethod
    def get_status(self, container_id: str) -> ContainerStatus:
        try:
            # Implementation
            ...
        except Exception as e:
            raise exceptions.ContainerNotFoundError(e) from e

    @abstractmethod
    def start(self, request: ContainerRequest, log_handler: LogHandler) -> str:
        # It returns the container id
        try:
            # Implementation
            ...
        except SpeficicImagePullError as e:
            raise exceptions.ContainerImagePullError(e) from e
        except Exception as e:
            raise exceptions.ContainerStartError(e) from e

    @abstractmethod
    def cleanup(self, container_id: str, log_handler: LogHandler) -> None:
        try:
            # Implementation
            ...
        except Exception as e:
            raise exceptions.ContainerCleanupError(e) from e

    @abstractmethod
    def update_logs(self, container_id: str, log_handler: LogHandler) -> None:
        try:
            # Implementation
            ...
        except Exception as e:
            raise exceptions.ContainerUpdateLogsError(e) from e


class SpeficicImagePullError(Exception):
    """Placeholder for the interface to raise specific image pull errors."""
