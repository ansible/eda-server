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
import shutil
import subprocess
from threading import Lock
from typing import Dict, List
from uuid import uuid4

from django.conf import settings

from aap_eda.core.enums import ActivationStatus, EDADeployment
from aap_eda.core.models import ActivationInstance, Ruleset
from aap_eda.core.utils import utcnow

LOG = logging.getLogger(__name__)
EDA_DEPLOY_SETTINGS = settings.EDA_DEPLOY_SETTINGS


class ExecutionDependencyException(Exception):
    pass


class ActivationExecutionFailed(Exception):
    pass


# FAIL FAST Dependency check!
ANSIBLE_RULEBOOK = shutil.which("ansible-rulebook")
if ANSIBLE_RULEBOOK is None:
    raise ExecutionDependencyException("ansible-rulebook not found")

SSH_AGENT = shutil.which("ssh-agent")
if SSH_AGENT is None:
    raise ExecutionDependencyException("ssh-agent not found")

if EDA_DEPLOY_SETTINGS.deployment_type == EDADeployment.DOCKER:
    import docker

    DOCKER_SOCKET_PATH = "/var/run/{client}.sock".format(
        client=EDADeployment.DOCKER.value.lower()
    )
    DOCKER_CLIENT_URI = f"unix://{DOCKER_SOCKET_PATH}"
    if not os.path.exists(DOCKER_SOCKET_PATH):
        raise ExecutionDependencyException(
            "Cannot find docker socket. Is docker running?"
        )
elif EDA_DEPLOY_SETTINGS.deployment_type == EDADeployment.PODMAN:
    import podman

    PODMAN_SOCKET_PATH = "/run/user/{uid}/{client}/{client}.sock".format(
        uid=os.getuid(), client=EDADeployment.PODMAN.value.lower()
    )
    # Sweet cuppin' cakes! make sure the protocol is "http+unix"!!!
    # TODO: If remote execution is needed, then this should be a value stored
    #       in the database somewhere.
    PODMAN_CLIENT_URI = f"http+unix://{PODMAN_SOCKET_PATH}"
    if not os.path.exists(PODMAN_SOCKET_PATH):
        raise ExecutionDependencyException(
            "Cannot find podman socket. podman should be running rootless."
        )
elif EDA_DEPLOY_SETTINGS.deployment_type != EDADeployment.LOCAL:
    not_implmented = NotImplementedError(
        "Deployment type {0} not implemented".format(
            EDA_DEPLOY_SETTINGS.deployment_type
        )
    )
    unknown_dependency = ExecutionDependencyException(
        "Unknown deployment type {0}".format(
            EDA_DEPLOY_SETTINGS.deployment_type
        )
    )
    raise not_implmented from unknown_dependency
# End dependency check


ACTIVATED_RULESETS_LOCK = Lock
ACTIVATED_RULESETS = {}


class ActivationExecution:
    def __init__(
        self,
        activation_instance: ActivationInstance,
    ):
        self._id = uuid4()
        self._container_deployments = (
            EDADeployment.DOCKER,
            EDADeployment.PODMAN,
        )
        self._activation_map = {
            EDADeployment.LOCAL: self.local_activate,
            EDADeployment.DOCKER: self.docker_activate,
            EDADeployment.PODMAN: self.podman_activate,
        }

        self.deployment_type = EDA_DEPLOY_SETTINGS.deployment_type
        self.activation_instance = activation_instance
        self.activation = self.activation_instance.activation
        self.rulesets = list(
            Ruleset.objects.filter(
                rulebook_id=self.activation.rulebook_id
            ).all()
        )
        if not self.rulesets:
            raise ActivationExecutionFailed(
                "No rulesets found for rulebook id "
                + str(self.activation.rulebook_id)
            )
        self.ruleset = self.rulesets[0]
        self.ruleset_source = (
            self.ruleset.sources[0] if self.ruleset.sources else {}
        )
        self.host = self.ruleset_source.get("config", {}).get(
            "host", EDA_DEPLOY_SETTINGS.deployment_host
        )
        self.port = self.ruleset_source.get("config", {}).get(
            "port", EDA_DEPLOY_SETTINGS.deployment_port
        )
        # TODO: Add log consumer

    @property
    def id(self):
        return self._id

    def log(self, msg: str, level: str = "info"):
        getattr(LOG, level)(f"EXECID: {self.id}:: {msg}")

    def _get_local_command(self) -> List:
        return [
            ANSIBLE_RULEBOOK,
            "--worker",
            "--websocket-address",
            f"ws://{self.host}:{self.port}/api/ws2",
            "--id",
            str(self.activation_instance.id),
        ]

    def _get_container_command(self) -> List:
        return [
            SSH_AGENT,
            ANSIBLE_RULEBOOK,
            "--worker",
            "--websocket-address",
            f"ws://{self.host}:{self.port}/api/ws2",
            "--id",
            str(self.activation_instance.id),
            "--debug",
        ]

    def _get_container_options(self) -> Dict:
        return {
            "environment": ["ANSIBLE_FORCE_COLOR=True"],
            "extra_hosts": {"host.docker.internal": "host-gateway"},
            "ports": {f"{self.port}/tcp": self.port, "8000/tcp": None},
            "network": "eda-network",
            "detach": False,
        }

    def _get_deployment_type_method(self):
        return self._activation_map[self.deployment_type]

    def add_activation_tracking(self):
        with ACTIVATED_RULESETS_LOCK():
            ACTIVATED_RULESETS[self.activation_instance.id] = self

    def deactivate(self):
        if self.deployment_type == EDADeployment.LOCAL:
            self.subprocess.kill()
        elif self.deployment_type in self._container_deployments:
            self.container.kill()
            self.container.remove()
            self.container_engine.close()

    def set_activation_status(self, status):
        self.activation_instance.status = status
        self.activation_instance.save()

    def activate(self):
        deployment_type_method = self._get_deployment_type_method()
        self.add_activation_tracking()

        try:
            deployment_type_method()
        except Exception as e:
            klass = self.__class__.__name__
            method = deployment_type_method.__name__
            self.log(f"{klass}.{method}: {e}", level="error")
            raise
        finally:
            pop_tracked_activation(self.activation_instance.id)

    def local_activate(self):
        cmd_args = self._get_local_command()

        self.log(ANSIBLE_RULEBOOK, level="debug")
        self.log(cmd_args, level="debug")
        self.log("Launching ansible-rulebook subprocess", level="debug")

        self.log(f"LOCAL ACTIVATION STARTS AT: {utcnow()}")
        self.set_activation_status(ActivationStatus.RUNNING)
        try:
            self.subprocess = subprocess.Popen(
                cmd_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            self.subprocess.wait()
        except Exception as e:
            self.set_activation_status(ActivationStatus.FAILED)
            raise ActivationExecutionFailed("Local execution failed!") from e
        else:
            self.set_activation_status(ActivationStatus.COMPLETED)
        finally:
            self.log(f"LOCAL ACTIVATION ENDS AT: {utcnow()}")

    def docker_activate(self):
        self.log("Launching ansible-rulebook docker container", level="debug")
        self.log("Host: %s", self.host, level="debug")
        self.log("Port: %s", self.port, level="debug")

        command = self.get_container_command()

        self.container_engine = docker.DockerClient(
            base_url=DOCKER_CLIENT_URI, version="auto", timeout=2
        )
        img = self.container_engine.images.pull(
            self.activation.execution_environment
        )

        container_options = self.get_container_options()
        self.container = self.container_engine.containers.create(
            img,
            command,
            **container_options,
        )
        # TODO: When adding a log consumer, you may want to
        #       change the detach option to True
        self.log(f"DOCKER ACTIVATION STARTS AT: {utcnow()}")
        self.set_activation_status(ActivationStatus.RUNNING)
        try:
            self.container.start()
        except Exception as e:
            self.set_activation_status(ActivationStatus.FAILED)
            raise ActivationExecutionFailed("Docker execution failed!") from e
        else:
            self.set_activation_status(ActivationStatus.COMPLETED)
        finally:
            self.log(f"DOCKER ACTIVATION ENDS AT: {utcnow()}")

    def podman_activate(self):
        self.log("Launching ansible-rulebook podman container")
        self.log("Host: %s", self.host, level="debug")
        self.log("Port: %s", self.port, level="debug")

        command = self.get_container_command()

        self.container_engine = podman.PodmanClient(
            base_url=PODMAN_CLIENT_URI, version="auto", timeout=2
        )
        img = self.container_engine.images.pull(
            self.activation.execution_environment
        )

        container_options = self.get_container_options()
        self.container = self.container_engine.containers.create(
            img,
            command,
            **container_options,
        )
        # TODO: When adding a log consumer, you may want to
        #       change the detach option to True
        self.log(f"PODMAN ACTIVATION STARTS AT: {utcnow()}")
        self.set_activation_status(ActivationStatus.RUNNING)
        try:
            self.container.start()
        except Exception as e:
            self.set_activation_status(ActivationStatus.FAILED)
            raise ActivationExecutionFailed("Podman execution failed!") from e
        else:
            self.set_activation_status(ActivationStatus.COMPLETED)
        finally:
            self.log(f"PODMAN ACTIVATION ENDS AT: {utcnow()}")


def pop_tracked_activation(activation_instance_id: int) -> ActivationExecution:
    with ACTIVATED_RULESETS_LOCK():
        execution = ACTIVATED_RULESETS.pop(activation_instance_id, None)

    if execution is None:
        raise ProcessLookupError(
            f"Activation instance ({activation_instance_id}) "
            + "has no running processes."
        )

    return execution


def deactivate_activation_instance(activation_instance: ActivationInstance):
    execution = pop_tracked_activation(activation_instance.id)
    execution.deactivate()

    return execution
