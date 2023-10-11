from abc import ABC, abstractmethod
from django.conf import settings
import aap_eda.core.models as models
import aap_eda.services.exceptions as exceptions
from dataclasses import dataclass


def new_container_engine():
    """Activation service factory.

    Returns an activation object based on the deployment type"""
    # TODO: deployment type should not be plain strings
    if settings.DEPLOYMENT_TYPE == "podman":
        return PodmanEngine()
    if settings.DEPLOYMENT_TYPE == "k8s":
        return K8sEngine()
    raise exceptions.InvalidDeploymentTypeError("Wrong deployment type")


class ActivationManager:
    def __init__(self, db_instance: models.Activation,
                 container_engine: ContainerEngine = new_container_engine()):
        self.db_instance = db_instance
        self.container_engine = container_engine

    def _set_status():
        pass


    def _get_status(self):
        db_status = None
        pod_state = self.container_engine.get_status()
        if db_status == pod_state:
            return ActivationStatus()

    def start(self):
        if self._get_status() == ActivationStatus.STARTING:
            return
        container = self.container_engine.start()
        self.db_instance.last_instance.container_id = container.get_id()

    def restart(self):
        pass

    def monitor(self):
        self.restart()

    def update_logs(self):
        pass

class ContainerEngine(ABC):
    """Abstract interface to connect to the deployment backend."""

    @abstractmethod
    def __init__(self):
        ...

    @abstractmethod
    def get_container(name_or_id: str) -> Container:
        ...

    @abstractmethod
    def start(self, ContainerRequest) -> Container:
        ...

    @abstractmethod
    def stop(self):
        ...

    @abstractmethod
    def restart(self):
        ...

    @abstractmethod
    def fetch_logs(self):
        ...

    @abstractmethod
    def get_status(self) -> ContainerStatus():
        ...


class PodmanEngine(ContainerEngine):
    def __init__(self, client = get_podman_client()):
        self.log_agent = PodmanLogAgent(engine=self)

    def start(self):
        pass

    def stop(self):
        pass

    def restart(self):
        pass

    def fetch_logs(self):
        pass

    def get_status(self):
        pass

    def get_container(name_or_id: str) -> Container:
        pass

class K8sEngine(ContainerEngine):
    def start(self):
        pass

    def stop(self):
        pass

    def restart(self):
        pass

    def fetch_logs(self):
        pass

    def get_status(self):
        pass


class PodmanLogAgent:
    def __init__(self, engine: PodmanEngine):
        self.engine = engine


def get_podman_client():
    pass



class Container:
    def __init__(self, status: str):
        self.status = status

    def get_id(self):
        ...


class k8sContainer(Container):
    def __init__(self, status: str):
        self.status = status

    def get_id(self):
        return se


class PodmanContainer(Container):
    def __init__(self, status: str):
        self.status = status

    def get_id(self):
        return se


@dataclass
class ContainerRequest:
    image:
    name: str
    memory_limits:
