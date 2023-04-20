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
import asyncio
import logging
import shutil
import subprocess
import uuid
from enum import Enum

from django.utils import timezone

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus

from .activation_docker import ActivationDocker
from .activation_kubernetes import ActivationKubernetes

logger = logging.getLogger(__name__)
WS_ADDRESS = "ws://{host}:{port}/api/eda/ws/ansible-rulebook"


class ActivateRulesetsFailed(Exception):
    pass


class DeploymentType(Enum):
    LOCAL = "local"
    DOCKER = "docker"
    PODMAN = "podman"
    K8S = "k8s"


class ActivateRulesets:
    def activate(
        self,
        activation_id: int,
        decision_environment_id: int,
        deployment_type: str,
        host: str,
        port: int,
    ):
        try:
            activation = models.Activation.objects.get(id=activation_id)
            instance = models.ActivationInstance.objects.create(
                activation_id=activation_id,
                name=activation.name,
                status=ActivationStatus.RUNNING,
            )

            decision_environment = models.DecisionEnvironment.objects.get(
                id=decision_environment_id
            )

            if decision_environment:
                decision_environment_url = decision_environment.image_url
            else:
                raise ActivateRulesetsFailed(
                    f"Unable to retrieve Decision Environment ID: "
                    f"{decision_environment_id}"
                )

            dtype = DeploymentType(deployment_type)

            if dtype == DeploymentType.LOCAL:
                self.activate_in_local(
                    ws_url=WS_ADDRESS.format(host=host, port=port),
                    activation_instance_id=instance.id,
                    decision_environment_url=decision_environment_url,
                )
            elif dtype == DeploymentType.PODMAN:
                self.activate_in_podman(
                    ws_url=WS_ADDRESS.format(host=host, port=port),
                    activation_instance_id=instance.id,
                    decision_environment_url=decision_environment_url,
                )
            elif dtype == DeploymentType.DOCKER:
                self.activate_in_docker_podman(
                    ws_url=WS_ADDRESS.format(host=host, port=port),
                    activation_instance_id=instance.id,
                    decision_environment_url=decision_environment_url,
                )

            elif dtype == DeploymentType.K8S:
                logger.info(f"Activation DeploymentType: {dtype}")
                self.activate_in_k8s(
                    ws_url=WS_ADDRESS.format(host=host, port=port),
                    activation_instance_id=instance.id,
                    decision_environment_url=decision_environment_url,
                )
            else:
                raise ActivateRulesetsFailed(f"Unsupported {deployment_type}")

            instance.status = ActivationStatus.COMPLETED
        except Exception as exe:
            logger.error(f"Activation error: {str(exe)}")
            instance.status = ActivationStatus.FAILED
        finally:
            instance.ended_at = timezone.now()
            instance.save()

    # TODO: (POC) call podman directly
    def activate_in_podman(
        self,
        ws_url: str,
        activation_instance_id: str,
        decision_environment_url: str,
    ) -> None:
        podman = shutil.which("podman")

        if podman is None:
            raise ActivateRulesetsFailed("command podman not found")

        podman_args = [
            "run",
            decision_environment_url,
            "ansible-rulebook",
            "--worker",
            "--websocket-address",
            ws_url,
            "--id",
            str(activation_instance_id),
        ]

        proc = self._run_subprocess(podman, podman_args)

        line_number = 0

        activation_instance_logs = []
        for line in proc.stdout.splitlines():
            activation_instance_log = models.ActivationInstanceLog(
                line_number=line_number,
                log=line,
                activation_instance_id=int(activation_instance_id),
            )
            activation_instance_logs.append(activation_instance_log)

            line_number += 1

        models.ActivationInstanceLog.objects.bulk_create(
            activation_instance_logs
        )
        logger.info(f"{line_number} of activation instance log are created.")

    def _run_subprocess(
        self, cmd: str, args: list[str]
    ) -> subprocess.CompletedProcess:
        try:
            # TODO: subprocess.run may run a while and will block the
            # following DB updates. Need to find a better way to solve it.
            return subprocess.run(
                [cmd, *args],
                check=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as exc:
            message = (
                f"Command returned non-zero exit status {exc.returncode}:"
                f"\n\tcommand: {exc.cmd}"
                f"\n\tstderr: {exc.stderr}"
            )
            logger.error("%s", message)
            raise ActivateRulesetsFailed(exc.stderr)

    def activate_in_local(
        self,
        ws_url: str,
        activation_instance_id: str,
        decision_environment_url: str,
    ) -> None:
        ansible_rulebook = shutil.which("ansible-rulebook")

        if ansible_rulebook is None:
            raise ActivateRulesetsFailed("command ansible-rulebook not found")

        local_args = [
            "--worker",
            "--websocket-address",
            ws_url,
            "--id",
            str(activation_instance_id),
        ]

        proc = self._run_subprocess(ansible_rulebook, local_args)

        line_number = 0

        activation_instance_logs = []
        for line in proc.stdout.splitlines():
            activation_instance_log = models.ActivationInstanceLog(
                line_number=line_number,
                log=line,
                activation_instance_id=int(activation_instance_id),
            )
            activation_instance_logs.append(activation_instance_log)

            line_number += 1

        models.ActivationInstanceLog.objects.bulk_create(
            activation_instance_logs
        )
        logger.info(f"{line_number} of activation instance log are created.")

    def activate_in_docker_podman(
        self,
        ws_url: str,
        activation_instance_id: str,
        decision_environment_url: str,
    ) -> None:
        docker = ActivationDocker(decision_environment_url)
        docker_cmd = [
            "ansible-rulebook",
            "--worker",
            "--websocket-address",
            ws_url,
            "--id",
            str(activation_instance_id),
        ]
        container = docker.run_container(docker_cmd)

        line_number = 0
        activation_instance_logs = []
        for line in container.logs(stream=True):
            activation_instance_log = models.ActivationInstanceLog(
                line_number=line_number,
                log=line.decode("ASCII"),
                activation_instance_id=int(activation_instance_id),
            )
            activation_instance_logs.append(activation_instance_log)

            line_number += 1

        models.ActivationInstanceLog.objects.bulk_create(
            activation_instance_logs
        )
        logger.info(f"{line_number} of activation instance log are created.")

    def activate_in_k8s(
        self,
        ws_url: str,
        activation_instance_id: str,
        decision_environment_url: str,
    ) -> None:
        k8s = ActivationKubernetes()
        _pull_policy = "Always"

        ns_fileref = open(
            "/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r"
        )
        namespace = ns_fileref.read()
        ns_fileref.close()

        guid = uuid.uuid4()
        job_name = f"activation-job-{guid}"
        pod_name = f"activation-pod-{guid}"

        # build out container,pod,job specs
        container_spec = k8s.create_container(
            image=decision_environment_url,
            name=pod_name,
            pull_policy=_pull_policy,
            url=ws_url,
            activation_id=activation_instance_id,
        )
        pod_spec = k8s.create_pod_template(
            pod_name=pod_name, container=container_spec
        )
        job_spec = k8s.create_job(
            job_name=job_name, pod_template=pod_spec, ttl=30
        )

        # execute job
        asyncio.run(
            k8s.run_activation_job(
                job_name=job_name,
                job_spec=job_spec,
                namespace=namespace,
                activation_instance_id=activation_instance_id,
            )
        )
