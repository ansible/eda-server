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
import uuid
from abc import ABC, abstractmethod
from datetime import datetime

import yaml
from django.conf import settings
from pydantic import BaseModel, validator

import aap_eda.services.activation.engine.exceptions as exceptions
from aap_eda.core.enums import ActivationStatus
from aap_eda.core.utils.credentials import inputs_from_store
from aap_eda.services.auth import create_jwt_token

from .ports import find_ports


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
    skip_audit_events: bool = False

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
        if self.skip_audit_events:
            args.append("--skip-audit-events")
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
    rulebook_process_id: int
    process_parent_id: int
    credential: tp.Optional[Credential] = None
    ports: tp.Optional[list[tuple]] = None
    pull_policy: str = settings.DEFAULT_PULL_POLICY  # Always by default
    mem_limit: tp.Optional[str] = None
    mounts: tp.Optional[list[dict]] = None
    env_vars: tp.Optional[dict] = None
    extra_args: tp.Optional[dict] = None
    k8s_service_name: tp.Optional[str] = None


class ContainerableMixinError(Exception):
    """Base class for exceptions from implementers of ContainerableMixin."""

    pass


class ContainerableInvalidError(ContainerableMixinError):
    pass


class ContainerableNoLatestInstanceError(ContainerableMixinError):
    pass


# To use ContainerableMixin the model class adding the mixin is required to
# have the following attributes (or property getters):
#
#   Attribute               Type
#   ---------               ----
#   decision_environment    DecisionEnvironment
#   extra_var               ExtraVar
#   latest_instance         RulebookProcess
#   restart_policy          str
#   rulebook_rulesets       str
#
class ContainerableMixin:
    def get_container_request(self) -> ContainerRequest:
        """Return ContainerRequest used for creation."""
        self.validate()

        return ContainerRequest(
            credential=self._get_image_credential(),
            name=self._get_container_name(),
            image_url=self.decision_environment.image_url,
            ports=self._get_ports(),
            process_parent_id=self.id,
            rulebook_process_id=self.latest_instance.id,
            env_vars=settings.PODMAN_ENV_VARS,
            extra_args=settings.PODMAN_EXTRA_ARGS,
            mem_limit=settings.PODMAN_MEM_LIMIT,
            mounts=settings.PODMAN_MOUNTS,
            cmdline=self._build_cmdline(),
            k8s_service_name=self._get_k8s_service_name(),
        )

    def get_restart_policy(self) -> str:
        """Return the restart policy for the implementer.

        We don't validate here as validation is for use to create a new
        container and the value of the restart policy is not a determinate of
        that.
        """
        return self.restart_policy

    def validate(self):
        """Validate the the implementer is appropriate to be containerized."""
        try:
            self._validate()
        except ContainerableMixinError as e:
            raise ContainerableInvalidError from e

    def _build_cmdline(self) -> AnsibleRulebookCmdLine:
        access_token, refresh_token = create_jwt_token()
        return AnsibleRulebookCmdLine(
            ws_url=self._get_ws_url(),
            log_level=self._get_log_level(),
            ws_ssl_verify=settings.WEBSOCKET_SSL_VERIFY,
            ws_access_token=access_token,
            ws_refresh_token=refresh_token,
            ws_token_url=self._get_ws_token_url(),
            heartbeat=settings.RULEBOOK_LIVENESS_CHECK_SECONDS,
            id=str(self.latest_instance.id),
            skip_audit_events=self._get_skip_audit_events(),
        )

    def _get_log_level(self) -> tp.Optional[str]:
        """Return the log level to use by ansible-rulebook."""
        level_map = {
            "debug": "-vv",
            "info": "-v",
            "error": None,
        }
        return level_map[self.log_level]

    def _get_container_name(self) -> str:
        """Return the name to use for the ContainerRequest."""
        return (
            f"{settings.CONTAINER_NAME_PREFIX}-{self.latest_instance.id}"
            f"-{uuid.uuid4()}"
        )

    def _get_context(self) -> dict[str, tp.Any]:
        """Return the context dictionary used to create a ContainerRquest."""
        if self.extra_var:
            context = yaml.safe_load(self.extra_var.extra_var)
        else:
            context = {}
        return context

    def _get_image_credential(self) -> tp.Optional[Credential]:
        """Return a decrypted Credential or None for the implementer."""
        credential = self.decision_environment.eda_credential
        if credential:
            inputs = inputs_from_store(credential.inputs.get_secret_value())
            return Credential(
                username=inputs["username"],
                secret=inputs["password"],
            )
        return None

    def _get_ports(self) -> list[tuple]:
        return find_ports(self.rulebook_rulesets, self._get_context())

    def _get_skip_audit_events(self) -> bool:
        """Return not skipping audit events as default."""
        return False

    def _get_ws_url(self) -> str:
        return f"{settings.WEBSOCKET_BASE_URL}{self._get_ws_url_subpath()}"

    def _get_ws_url_subpath(self) -> str:
        return f"/{settings.API_PREFIX}/ws/ansible-rulebook"

    def _get_ws_token_url(self) -> str:
        return (
            f"{settings.WEBSOCKET_TOKEN_BASE_URL}"
            f"{self._get_ws_token_url_subpath()}"
        )

    def _get_ws_token_url_subpath(self) -> str:
        return f"/{settings.API_PREFIX}/v1/auth/token/refresh/"

    def _validate(self):
        if not self.latest_instance:
            raise ContainerableNoLatestInstanceError

    def _get_k8s_service_name(self):
        return self.k8s_service_name or settings.K8S_SERVICE_NAME


class ContainerStatus(BaseModel):
    status: ActivationStatus
    message: str = ""


class ContainerEngine(ABC):
    """Abstract interface to connect to the deployment backend."""

    @abstractmethod
    def __init__(self, activation_id: str, resource_prefix: str):
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
