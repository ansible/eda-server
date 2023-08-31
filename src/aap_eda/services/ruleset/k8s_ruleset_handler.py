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

from django.conf import settings

from aap_eda.core import models

from .activation_db_logger import ActivationDbLogger
from .activation_kubernetes import ActivationKubernetes
from .ruleset_handler import RulesetHandler

logger = logging.getLogger(__name__)


class K8SRulesetHandler(RulesetHandler):
    def activate(
        self,
        instance: models.ActivationInstance,
        activation_db_logger: ActivationDbLogger,
    ) -> models.ActivationInstance:
        activation = instance.activation
        decision_environment = activation.decision_environment

        k8s = ActivationKubernetes()
        _pull_policy = "Always"

        ns_fileref = open(
            "/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r"
        )
        namespace = ns_fileref.read()
        ns_fileref.close()

        activation_id = activation.pk
        job_name = f"activation-job-{activation_id}-{instance.id}"
        pod_name = f"activation-pod-{activation_id}-{instance.id}"

        # build out container,pod,job specs
        container_spec = k8s.create_container(
            image=decision_environment.image_url,
            name=pod_name,
            pull_policy=_pull_policy,
            activation_instance_id=instance.id,
            ports=[
                port
                for _, port in super().find_ports(
                    instance.activation.rulebook_rulesets
                )
            ],
            heartbeat=settings.RULEBOOK_LIVENESS_CHECK_SECONDS,
        )

        secret_name = None
        if decision_environment.credential:
            secret_name = f"activation-secret-{activation_id}"
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
            job_name=job_name,
            activation_id=str(activation_id),
            pod_template=pod_spec,
            ttl=30,
        )

        for _, port in super().find_ports(
            instance.activation.rulebook_rulesets
        ):
            k8s.create_service(
                namespace=namespace, job_name=job_name, port=port
            )

        # execute job
        k8s.run_activation_job(
            job_name=job_name,
            job_spec=job_spec,
            namespace=namespace,
            activation_instance=instance,
            secret_name=secret_name,
        )

    def deactivate(
        self,
        instance: models.ActivationInstance,
    ):
        logger("K8SRulesetsHandler deactivate() is called")
        k8s = ActivationKubernetes()

        ns_fileref = open(
            "/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r"
        )
        namespace = ns_fileref.read()
        ns_fileref.close()

        logger.debug(f"namespace: {namespace}")
        logger.debug(f"activation_name: {instance.name}")
        k8s.delete_job(instance, namespace)
