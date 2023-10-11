from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


class ContainerEngine(ABC):
    """Abstract interface to connect to the deployment backend."""

    @abstractmethod
    def __init__(
        self,
    ):
        ...

    @abstractmethod
    def get_status(container_id: str) -> str:
        ...

    @abstractmethod
    def start(self, ContainerRequest) -> str:
        ...

    @abstractmethod
    def stop(self, container_id: str):
        ...

    @abstractmethod
    def restart(self, container_id: str):
        ...

    @abstractmethod
    def update_logs(self, container_id: str):
        ...


# TODO: use pydantic
@dataclass
class AnsibleRulebookCmdLine:
    ws_url: str
    ws_ssl_verify: str
    heartbeat: int
    id: str
    log_level: str  # -v or -vv or None

    def to_args(self) -> dict:
        args = [
            "ansible-rulebook",
            "--worker",
            "--websocket-ssl-verify",
            self.ws_ssl_verify,
            "--websocket-address",
            self.ws_url,
            "--id",
            self.id,
            "--heartbeat",
            str(self.heartbeat),
        ]
        if self.log_level:
            args.append(self.log_level)

        return args


# TODO: use pydantic
@dataclass
class Credential:
    username: str

    def get_password() -> str:
        pass

    def get_token() -> str:
        pass


# TODO: use pydantic
@dataclass
class ContainerRequest:
    name: str  # f"eda-{activation_instance.id}-{uuid.uuid4()}"
    image_url: str  # quay.io/ansible/ansible-rulebook:main
    credential: Credential
    ports: dict
    cmdline: AnsibleRulebookCmdLine
    mem_limit: str
    mounts: dict
    env_vars: dict
    extra_args: dict


class LogHandler(ABC):
    @abstractmethod
    def write(self, line: str, flush: bool) -> None:
        pass

    @abstractmethod
    def get_log_read_at(self) -> datetime:
        pass

    @abstractmethod
    def set_log_read_at(self, dt):
        pass

    @abstractmethod
    def flush() -> None:
        pass
