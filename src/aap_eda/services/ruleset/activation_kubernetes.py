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
import time

from django.conf import settings
from kubernetes import client, config, watch

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.services.ruleset.exceptions import K8sActivationException

from .shared_settings import VALID_LOG_LEVELS

logger = logging.getLogger(__name__)


class ActivationKubernetes:
    def __init__(self):
        # Setup kubernetes api client
        config.load_incluster_config()

        self.batch_api = client.BatchV1Api()
        self.client_api = client.CoreV1Api()
        self.network_api = client.NetworkingV1Api()

    @staticmethod
    def create_container(
        image,
        name,
        pull_policy,
        url,
        ssl_verify,
        activation_id,
        ports,
        heartbeat,
    ) -> client.V1Container:
        args = [
            "--worker",
            "--websocket-address",
            url,
            "--websocket-ssl-verify",
            ssl_verify,
            "--id",
            str(activation_id),
            "--heartbeat",
            str(heartbeat),
        ]
        if (
            settings.ANSIBLE_RULEBOOK_LOG_LEVEL
            and settings.ANSIBLE_RULEBOOK_LOG_LEVEL in VALID_LOG_LEVELS
        ):
            args.append(settings.ANSIBLE_RULEBOOK_LOG_LEVEL)

        container = client.V1Container(
            image=image,
            name=name,
            image_pull_policy=pull_policy,
            env=[client.V1EnvVar(name="ANSIBLE_LOCAL_TEMP", value="/tmp")],
            args=args,
            ports=[
                client.V1ContainerPort(container_port=port) for port in ports
            ],
            command=["ansible-rulebook"],
        )

        logger.info(
            f"Created container: name: {container.name}, "
            f"image: {container.image} "
            f"args: {container.args}"
        )

        return container

    def create_secret(
        self,
        secret_name: str,
        namespace: str,
        decision_environment: models.DecisionEnvironment,
    ) -> None:
        credential = decision_environment.credential
        server = decision_environment.image_url.split("/")[0]
        cred_payload = {
            "auths": {
                server: {
                    "username": credential.username,
                    "password": credential.secret.get_secret_value(),
                }
            }
        }

        data = {
            ".dockerconfigjson": base64.b64encode(
                json.dumps(cred_payload).encode()
            ).decode()
        }

        secret = client.V1Secret(
            api_version="v1",
            data=data,
            kind="Secret",
            metadata={"name": secret_name, "namespace": namespace},
            type="kubernetes.io/dockerconfigjson",
        )

        self.client_api.create_namespaced_secret(
            namespace=namespace,
            body=secret,
        )

    @staticmethod
    def create_pod_template(
        pod_name, container, secret_name
    ) -> client.V1PodTemplateSpec:
        if secret_name:
            spec = client.V1PodSpec(
                restart_policy="Never",
                containers=[container],
                image_pull_secrets=[
                    client.V1LocalObjectReference(secret_name)
                ],
            )
        else:
            spec = client.V1PodSpec(
                restart_policy="Never", containers=[container]
            )

        pod_template = client.V1PodTemplateSpec(
            spec=spec,
            metadata=client.V1ObjectMeta(name=pod_name, labels={"app": "eda"}),
        )

        logger.info(f"Created Pod template: {pod_name}")

        return pod_template

    def create_service(self, job_name, port, namespace):
        service_template = client.V1Service(
            spec=client.V1ServiceSpec(
                selector={"app": "eda", "job-name": job_name},
                ports=[
                    client.V1ServicePort(
                        protocol="TCP", port=port, target_port=port
                    )
                ],
            ),
            metadata=client.V1ObjectMeta(
                name=f"{job_name}-{port}",
                labels={"app": "eda", "job-name": job_name},
                namespace=namespace,
            ),
        )

        logger.info(f"Create Service: {job_name}")
        self.client_api.create_namespaced_service(namespace, service_template)

    @staticmethod
    def create_job(
        job_name, activation_name, pod_template, backoff_limit=0, ttl=0
    ) -> client.V1Job:
        metadata = client.V1ObjectMeta(
            name=job_name,
            labels={
                "job-name": job_name,
                "app": "eda",
                "activation-name": activation_name,
            },
        )

        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=metadata,
            spec=client.V1JobSpec(
                backoff_limit=backoff_limit,
                template=pod_template,
                ttl_seconds_after_finished=ttl,
            ),
        )

        logger.info(f"Created Job template: {job_name},")

        return job

    def delete_job(self, activation_instance, namespace) -> None:
        try:
            instance_name = activation_instance.name
            activation_job = self.batch_api.list_namespaced_job(
                namespace=namespace,
                label_selector=f"activation-name={instance_name}",
                timeout_seconds=0,
            )

            if activation_job is None:
                logger.info(f"Unable to find running Job for {instance_name}")
                raise K8sActivationException(
                    f"Unable to find running Job for {instance_name}"
                )

            status = self.batch_api.delete_namespaced_job(
                name=activation_job.items[0].metadata.name,
                namespace=namespace,
                propagation_policy="Background",
            )

            if status.status == "Failure":
                raise K8sActivationException(f"{status}")

            logger.info(f"Stop Activation {instance_name}: {status.status}")
            self.set_activation_status(
                activation_instance, ActivationStatus.STOPPED
            )

        except Exception as e:
            raise K8sActivationException(
                f"Stop {instance_name} Failed: \n {e}"
            )

    def run_activation_job(
        self,
        job_name,
        job_spec,
        namespace,
        activation_instance,
        secret_name,
    ) -> None:
        logger.info(f"Create Job: {job_name}")
        self.batch_api.create_namespaced_job(
            namespace=namespace, body=job_spec, async_req=True
        )
        w = watch.Watch()

        done = False
        while not done:
            try:
                for event in w.stream(
                    self.batch_api.list_namespaced_job,
                    namespace=namespace,
                    label_selector=f"job-name={job_name}",
                    timeout_seconds=0,
                ):
                    o = event["object"]
                    obj_name = o.metadata.name

                    if o.status.succeeded:
                        logger.info(f"Job {obj_name}: Succeeded")
                        done = True
                        w.stop()

                    if o.status.active:
                        logger.info(f"Job {obj_name}: Active")
                        self.watch_job_pod(
                            job_name=job_name,
                            namespace=namespace,
                            activation_instance=activation_instance,
                        )

                        done = True
                        w.stop()

                    if o.status.failed:
                        logger.info(f"Job {obj_name}: Failed")
                        w.stop()
                        raise K8sActivationException()

            except Exception as e:
                raise K8sActivationException(f"Job {obj_name} Failed: \n {e}")

            finally:
                # remove secret if created
                if secret_name:
                    self.delete_secret(
                        secret_name=secret_name,
                        namespace=namespace,
                        job_name=job_name,
                    )

    def delete_secret(self, secret_name, namespace, job_name) -> None:
        # wait until job is done
        while True:
            ret = client.BatchV1Api().list_namespaced_job(
                namespace=namespace,
                field_selector=f"metadata.name={job_name}",
            )
            if not ret.items[0].status.active:
                break

            time.sleep(1)

        logger.info(f"Removing secret: {secret_name}")

        self.client_api.delete_namespaced_secret(
            name=secret_name,
            namespace=namespace,
        )

    def log_job_to_db(self, log, activation_instance_id) -> None:
        line_number = 0
        activation_instance_logs = []
        for line in log.splitlines():
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

    def set_activation_status(
        self, instance: models.ActivationInstance, status: ActivationStatus
    ) -> None:
        instance.status = status
        instance.save(update_fields=["status"])

    def watch_job_pod(self, job_name, namespace, activation_instance) -> None:
        w = watch.Watch()

        done = False
        while not done:
            try:
                for event in w.stream(
                    self.client_api.list_namespaced_pod,
                    namespace=namespace,
                    label_selector=f"job-name={job_name}",
                ):
                    if event["object"].status.phase == "Pending":
                        pod_name = event["object"].metadata.name
                        logger.info(f"Pod {pod_name} - Pending")

                    if event["object"].status.phase == "Running":
                        pod_name = event["object"].metadata.name
                        logger.info(f"Pod {pod_name} - Running")
                        self.set_activation_status(
                            instance=activation_instance,
                            status=ActivationStatus.RUNNING,
                        )
                        self.read_job_pod_log(
                            pod_name=pod_name,
                            namespace=namespace,
                            activation_instance_id=activation_instance.id,
                        )

                    if event["object"].status.phase == "Succeeded":
                        pod_name = event["object"].metadata.name
                        logger.info(f"Pod {pod_name} - Succeeded")

                        self.read_job_pod_log(
                            pod_name=pod_name,
                            namespace=namespace,
                            activation_instance_id=activation_instance.id,
                        )
                        w.stop()
                        done = True

                    if event["object"].status.phase == "Failed":
                        pod_name = event["object"].metadata.name
                        logger.info(f"Pod {pod_name} - Failed")

                        self.read_job_pod_log(
                            pod_name=pod_name,
                            namespace=namespace,
                            activation_instance_id=activation_instance.id,
                        )
                        w.stop()
                        raise K8sActivationException()

            except Exception as e:
                raise K8sActivationException(f"Pod {pod_name} Failed: \n {e}")

    def read_job_pod_log(
        self, pod_name, namespace, activation_instance_id
    ) -> None:
        w = watch.Watch()
        done = False
        line_number = 0

        while not done:
            try:
                for line in w.stream(
                    self.client_api.read_namespaced_pod_log,
                    name=pod_name,
                    namespace=namespace,
                    pretty=True,
                ):
                    # log info to worker log
                    logger.info(line)

                    # log info to DB
                    activation_instance_log = models.ActivationInstanceLog(
                        line_number=line_number,
                        log=line,
                        activation_instance_id=activation_instance_id,
                    )
                    activation_instance_log.save()

                    line_number += 1

                done = True
            except Exception as e:
                raise K8sActivationException(
                    f"Failed to read pod logs: \n {e}"
                )
