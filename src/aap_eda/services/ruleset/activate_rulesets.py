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
import uuid
from enum import Enum
from typing import Optional

from django.utils import timezone

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus

from .activation_kubernetes import ActivationKubernetes
from .ansible_rulebook import AnsibleRulebookService

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
    def __init__(self, cwd: Optional[str] = None):
        self.service = AnsibleRulebookService(cwd)

    def activate(
        self,
        activation_id: int,
        decision_environment: str,
        deployment_type: str,
        host: str,
        port: int,
    ):
        try:
            instance = models.ActivationInstance.objects.create(
                activation_id=activation_id
            )
            instance.status = ActivationStatus.RUNNING

            dtype = DeploymentType(deployment_type)

            if dtype == DeploymentType.LOCAL:
                self.activate_in_local(
                    WS_ADDRESS.format(host=host, port=port), instance.id
                )
            elif (
                dtype == DeploymentType.PODMAN
                or dtype == DeploymentType.DOCKER
            ):
                self.activate_in_docker_podman()

            elif dtype == DeploymentType.K8S:
                logger.info(f"Activation DeploymentType: {dtype}")
                self.activate_in_k8s(
                    WS_ADDRESS.format(host=host, port=port), instance.id
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

    def activate_in_local(
        self,
        url: str,
        activation_instance_id: str,
    ) -> None:
        ssh_agent = shutil.which("ssh-agent")
        ansible_rulebook = shutil.which("ansible-rulebook")

        if ansible_rulebook is None:
            raise ActivateRulesetsFailed("command ansible-rulebook not found")

        if ssh_agent is None:
            raise ActivateRulesetsFailed("command ssh-agent not found")

        proc = self.service.run_worker_mode(
            ssh_agent, ansible_rulebook, url, activation_instance_id
        )

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

    # TODO(hsong) implement later
    def activate_in_docker_podman():
        pass

    def activate_in_k8s(
        self,
        url: str,
        activation_instance_id: str,
    ) -> None:
        k8s = ActivationKubernetes()

        # TODO: These DE values will be configurable(passed in)
        # Decision Environment (DE)
        _decision_environment = "quay.io/ansible/ansible-rulebook:main"
        _decision_environment_name = "ansible-rulebook"
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
            image=_decision_environment,
            name=_decision_environment_name,
            pull_policy=_pull_policy,
            url=url,
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
                namespace=namespace
            )
        )
