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
import shutil
import uuid
from enum import Enum
from typing import Optional

from django.conf import settings
from django.utils import timezone

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus

from .activation_kubernetes import ActivationKubernetes
from .activation_podman import ActivationPodman
from .ansible_rulebook import AnsibleRulebookService
from .exceptions import ActivationException

logger = logging.getLogger(__name__)
ACTIVATION_PATH = "/api/eda/ws/ansible-rulebook"


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
        decision_environment_id: int,
        deployment_type: str,
        ws_base_url: str,
        ssl_verify: str,
    ):
        try:
            activation = models.Activation.objects.get(id=activation_id)
            instance = models.ActivationInstance.objects.create(
                activation_id=activation_id,
                name=activation.name,
                status=ActivationStatus.STARTING,
            )
            instance.save()

            decision_environment = models.DecisionEnvironment.objects.get(
                id=decision_environment_id
            )

            try:
                dtype = DeploymentType(deployment_type)
            except ValueError:
                raise ActivationException(
                    f"Invalid deployment type: {deployment_type}"
                )

            ws_url = f"{ws_base_url}{ACTIVATION_PATH}"

            if dtype == DeploymentType.LOCAL:
                self.activate_in_local(ws_url, ssl_verify, instance.id)
            elif dtype == DeploymentType.PODMAN:
                self.activate_in_podman(
                    ws_url=ws_url,
                    ssl_verify=ssl_verify,
                    activation_instance_id=instance.id,
                    decision_environment=decision_environment,
                )
            elif dtype == DeploymentType.DOCKER:
                self.activate_in_docker()

            elif dtype == DeploymentType.K8S:
                logger.info(f"Activation DeploymentType: {dtype}")
                self.activate_in_k8s(
                    ws_url=ws_url,
                    ssl_verify=ssl_verify,
                    activation_instance=instance,
                    decision_environment=decision_environment,
                )
            else:
                raise ActivationException(f"Unsupported {deployment_type}")

            instance.status = ActivationStatus.COMPLETED
        except ActivationException as exe:
            logger.error(f"Activation error: {str(exe)}")
            instance.status = ActivationStatus.FAILED
        finally:
            instance.ended_at = timezone.now()
            instance.save()

    def activate_in_local(
        self,
        url: str,
        ssl_verify: str,
        activation_instance_id: str,
    ) -> None:
        ssh_agent = shutil.which("ssh-agent")
        ansible_rulebook = shutil.which("ansible-rulebook")

        if ansible_rulebook is None:
            raise ActivationException("command ansible-rulebook not found")

        if ssh_agent is None:
            raise ActivationException("command ssh-agent not found")

        proc = self.service.run_worker_mode(
            ssh_agent,
            ansible_rulebook,
            url,
            ssl_verify,
            activation_instance_id,
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

    def activate_in_podman(
        self,
        ws_url: str,
        ssl_verify: str,
        activation_instance_id: str,
        decision_environment: models.DecisionEnvironment,
    ) -> None:
        podman = ActivationPodman(
            decision_environment, settings.PODMAN_SOCKET_URL
        )
        container = podman.run_worker_mode(
            ws_url=ws_url,
            ws_ssl_verify=ssl_verify,
            activation_instance_id=activation_instance_id,
        )

        line_number = 0

        activation_instance_logs = []
        for line in container.logs():
            activation_instance_log = models.ActivationInstanceLog(
                line_number=line_number,
                log=line.decode("utf-8"),
                activation_instance_id=int(activation_instance_id),
            )
            activation_instance_logs.append(activation_instance_log)

            line_number += 1

        models.ActivationInstanceLog.objects.bulk_create(
            activation_instance_logs
        )
        logger.info(f"{line_number} of activation instance log are created.")

    # TODO(hsong) implement later
    def activate_in_docker():
        pass

    def activate_in_k8s(
        self,
        ws_url: str,
        ssl_verify: str,
        activation_instance: models.ActivationInstance,
        decision_environment: models.DecisionEnvironment,
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
            image=decision_environment.image_url,
            name=pod_name,
            pull_policy=_pull_policy,
            url=ws_url,
            ssl_verify=ssl_verify,
            activation_id=activation_instance.id,
        )

        secret_name = None
        if decision_environment.credential:
            secret_name = f"activation-secret-{guid}"
            k8s.create_secret(
                secret_name=secret_name,
                namespace=namespace,
                decision_environment=decision_environment,
            )

        pod_spec = k8s.create_pod_template(
            pod_name=pod_name,
            container=container_spec,
            secret_name=secret_name,
        )

        job_spec = k8s.create_job(
            job_name=job_name, pod_template=pod_spec, ttl=30
        )

        # execute job
        k8s.run_activation_job(
            job_name=job_name,
            job_spec=job_spec,
            namespace=namespace,
            activation_instance=activation_instance,
            secret_name=secret_name,
        )
