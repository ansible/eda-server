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
from dataclasses import dataclass
from datetime import datetime, timezone
from dateutil import parser

from kubernetes import client as k8sclient, config, watch
from kubernetes.client.rest import ApiException

from aap_eda.core.enums import ActivationStatus
from aap_eda.services.activation.exceptions import (
    ActivationException,
    ActivationPodNotFound,
    DeactivationException,
    K8sActivationException,
)

from .common import ContainerEngine, ContainerRequest, LogHandler

LOGGER = logging.getLogger(__name__)
SUCCESSFUL_EXIT_CODES = [0, 143]
KEEP_JOBS_FOR_SECONDS = 300


@dataclass
class Client:
    batch_api: k8sclient.BatchV1Api
    core_api: k8sclient.CoreV1Api
    network_api: k8sclient.NetworkingV1Api


def get_k8s_client():
    """K8S client factory."""
    # Setup kubernetes api client
    config.load_incluster_config()

    return Client(
        batch_api=k8sclient.BatchV1Api(),
        core_api=k8sclient.CoreV1Api(),
        network_api=k8sclient.NetworkingV1Api(),
    )


class Engine(ContainerEngine):
    def __init__(
        self,
        activation_id: str,
        client=None,
    ) -> None:
        if client:
            self.client = client
        else:
            self.client = get_k8s_client()
        self._set_namespace()
        self.secret_name = f"activation-secret-{activation_id}"

    def stop(self, container_id: str, log_handler: LogHandler) -> None:
        self._cleanup(container_id, log_handler)

    def start(self, request: ContainerRequest, log_handler: LogHandler) -> str:
        # TODO : Should this be compatible with the previous version
        # Previous Version
        self.job_name = f"activation-job-{request.parent_id}-{request.id}"
        self.pod_name = f"activation-pod-{request.parent_id}-{request.id}"

        # Should we switch to new format
        # self.job_name = f"activation-job-" #noqa: E800
        # f"{request.id}-{uuid.uuid4()}" #noqa: E800
        try:
            log_handler.write("Creating Job")
            log_handler.write(f"Image URL is {request.image_url}", True)
            self._create_job(request)
            LOGGER.info("Waiting for pod to start")
            self._wait_for_pod_to_start()
            if request.ports:
                for port in self._get_ports(request.ports):
                    self._create_service(port)
            LOGGER.info("Job is running")
            log_handler.write("Job is running")
            return self.job_name
        except (
            ActivationException,
            DeactivationException,
            K8sActivationException,
        ) as e:
            LOGGER.error("Failed to start job, doing cleanup")
            LOGGER.error(e)
            self._cleanup(self.job_name, log_handler)
            raise

    # note(alex): the signature of this method is different from the interface
    def get_status(self, job_name) -> ActivationStatus:
        status = ActivationStatus.FAILED
        LOGGER.info(f"in get_status for {job_name}")
        # TODO: catch kubernetes exception and raise custom exception
        pod = self._get_job_pod(job_name)

        container_status = pod.status.container_statuses[0]
        if container_status.state.running:
            status = ActivationStatus.RUNNING
        elif container_status.state.terminated:
            exit_code = container_status.state.terminated.exit_code
            if exit_code in SUCCESSFUL_EXIT_CODES:
                status = ActivationStatus.COMPLETED
                LOGGER.info("Pod has successfully exited")
            else:
                status = ActivationStatus.FAILED
                LOGGER.info(
                    f"Pod exited with {exit_code}, reason "
                    f"{container_status.state.terminated.reason}"
                )
        LOGGER.info(f"get_status {job_name} current status {status}")
        return status

    def _get_ports(self, found_ports: dict) -> list:
        return [port for _, port in found_ports]

    def _cleanup(self, job_name: str, log_handler: LogHandler):
        self.job_name = job_name
        self._delete_secret()
        self._delete_services()
        self._delete_job()

    def update_logs(self, container_id: str, log_handler: LogHandler) -> None:
        try:
            pod = self._get_job_pod(container_id)
            container_status = pod.status.container_statuses[0]
            if (
                container_status.state.running
                or container_status.state.terminated
            ):
                log_args = {
                    "name": pod.metadata.name,
                    "namespace": self.namespace,
                    "timestamps": True,
                }

                if log_handler.get_log_read_at():
                    current_dt = datetime.fromtimestamp(
                        time.time_ns() / 1e9, timezone.utc
                    )
                    log_args["since_seconds"] = (
                        current_dt - log_handler.get_log_read_at()
                    ).seconds

                log = self.client.core_api.read_namespaced_pod_log(**log_args)
                timestamp = None

                for line in log.splitlines():
                    timestamp, content = line.split(" ", 1)
                    log_handler.write(content)

                if timestamp:
                    dt = parser.parse(timestamp)
                    log_handler.flush()
                    log_handler.set_log_read_at(dt)
            else:
                LOGGER.warning(f"Pod with label {container_id} not found.")
                log_handler.write(
                    f"Pod with label {container_id} not found.", True
                )
        except ApiException as e:
            LOGGER.exception(
                "Failed to fetch pod logs: " f"{container_id}; error: {str(e)}"
            )
            raise

    def _get_job_pod(self, job_name) -> k8sclient.V1PodList:
        job_label = f"job-name={job_name}"
        result = self.client.core_api.list_namespaced_pod(
            namespace=self.namespace, label_selector=job_label
        )
        if not result.items:
            raise ActivationPodNotFound(
                f"Pod with label {job_label} not found"
            )
        return result.items[0]

    def _create_container(
        self,
        request: ContainerRequest,
    ) -> k8sclient.V1Container:
        ports = []
        if request.ports:
            ports = [
                k8sclient.V1ContainerPort(container_port=port)
                for port in self._get_ports(request.ports)
            ]
        container = k8sclient.V1Container(
            image=request.image_url,
            name=request.name,
            image_pull_policy=request.pull_policy,
            env=[k8sclient.V1EnvVar(name="ANSIBLE_LOCAL_TEMP", value="/tmp")],
            args=request.cmdline.get_args(),
            ports=ports,
            command=[request.cmdline.command()],
        )

        LOGGER.info(
            f"Created container: name: {container.name}, "
            f"image: {container.image} "
            f"args: {container.args}"
        )
        return container

    def _create_pod_template(
        self, request: ContainerRequest
    ) -> k8sclient.V1PodTemplateSpec:
        container = self._create_container(request)
        if request.credential:
            self._create_secret(request)
            spec = k8sclient.V1PodSpec(
                restart_policy="Never",
                containers=[container],
                image_pull_secrets=[
                    k8sclient.V1LocalObjectReference(self.secret_name)
                ],
            )
        else:
            spec = k8sclient.V1PodSpec(
                restart_policy="Never", containers=[container]
            )

        pod_template = k8sclient.V1PodTemplateSpec(
            spec=spec,
            metadata=k8sclient.V1ObjectMeta(
                name=self.pod_name,
                labels={"app": "eda", "job-name": self.job_name},
            ),
        )

        LOGGER.info(f"Created Pod template: {self.pod_name}")
        LOGGER.info(f"{pod_template}")
        return pod_template

    def _create_service(self, port):
        # only create the service if it does not already exist
        service_name = f"{self.job_name}-{port}"

        # TODO: catch kubernetes exception and raise custom exception
        service = self.client.core_api.list_namespaced_service(
            namespace=self.namespace,
            field_selector=f"metadata.name={service_name}",
        )

        if not service.items:
            service_template = k8sclient.V1Service(
                spec=k8sclient.V1ServiceSpec(
                    selector={"app": "eda", "job-name": self.job_name},
                    ports=[
                        k8sclient.V1ServicePort(
                            protocol="TCP", port=port, target_port=port
                        )
                    ],
                ),
                metadata=k8sclient.V1ObjectMeta(
                    name=f"{service_name}",
                    labels={"app": "eda", "job-name": self.job_name},
                    namespace=self.namespace,
                ),
            )

            self.client.core_api.create_namespaced_service(
                self.namespace, service_template
            )
            LOGGER.info(f"Created Service: {service_name}")
        else:
            LOGGER.info(f"Service already exists: {service_name}")

    def _delete_services(self) -> None:
        services = self.client.core_api.list_namespaced_service(
            namespace=self.namespace,
            label_selector=f"job-name={self.job_name}",
        )

        for svc in services.items:
            service_name = svc.metadata.name

            self.client.core_api.delete_namespaced_service(
                name=service_name,
                namespace=self.namespace,
            )
            LOGGER.info(f"Service {service_name} is deleted")

    def _create_job(
        self,
        request: ContainerRequest,
        backoff_limit=0,
        ttl=KEEP_JOBS_FOR_SECONDS,
    ) -> k8sclient.V1Job:
        pod_template = self._create_pod_template(request)

        metadata = k8sclient.V1ObjectMeta(
            name=self.job_name,
            labels={
                "job-name": self.job_name,
                "app": "eda",
            },
        )

        job_spec = k8sclient.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=metadata,
            spec=k8sclient.V1JobSpec(
                backoff_limit=backoff_limit,
                template=pod_template,
                ttl_seconds_after_finished=ttl,
            ),
        )

        LOGGER.info(f"{job_spec}")
        # TODO: catch kubernetes exception and raise custom exception
        job_result = self.client.batch_api.create_namespaced_job(
            namespace=self.namespace, body=job_spec
        )
        LOGGER.info(f"Submitted Job template: {self.job_name},")

        return job_result

    def _delete_job(self) -> None:
        try:
            activation_job = self.client.batch_api.list_namespaced_job(
                namespace=self.namespace,
                label_selector=f"job-name={self.job_name}",
                timeout_seconds=0,
            )

            if activation_job.items and activation_job.items[0].metadata:
                activation_job_name = activation_job.items[0].metadata.name
                result = self.client.batch_api.delete_namespaced_job(
                    name=activation_job_name,
                    namespace=self.namespace,
                    propagation_policy="Background",
                )

                if result.status == "Failure":
                    raise K8sActivationException(f"{result}")
            else:
                LOGGER.info(f"Job for : {self.job_name} has been removed")

        except ApiException as e:
            raise K8sActivationException(
                f"Stop of {self.job_name} Failed: \n {e}"
            )

    def _wait_for_pod_to_start(self) -> ActivationStatus:
        watcher = watch.Watch()
        pod_failed_reasons = [
            "InvalidImageName",
            "ImagePullBackOff",
            "ErrImagePull",
        ]
        status = ActivationStatus.PENDING
        LOGGER.info("Waiting for pod to start")
        while True:
            try:
                for event in watcher.stream(
                    self.client.core_api.list_namespaced_pod,
                    namespace=self.namespace,
                    label_selector=f"job-name={self.job_name}",
                ):
                    if event["object"].status.phase == "Pending":
                        pod_name = event["object"].metadata.name
                        LOGGER.info(f"Pod {pod_name} - Pending")

                        statuses = event["object"].status.container_statuses

                        if statuses and statuses[0]:
                            LOGGER.info(f"CONT STATUS: {statuses[0]}")

                            if statuses[0].state.waiting:
                                message = statuses[0].state.waiting.message
                                reason = statuses[0].state.waiting.reason
                                if reason in pod_failed_reasons:
                                    # self._delete_job()  move to the caller
                                    status = ActivationStatus.ERROR
                                    raise K8sActivationException(message)

                    if event["object"].status.phase == "Running":
                        pod_name = event["object"].metadata.name
                        LOGGER.info(f"Pod {pod_name} - Running")
                        status = ActivationStatus.RUNNING
                        break

                    if event["object"].status.phase == "Succeeded":
                        pod_name = event["object"].metadata.name
                        LOGGER.info(f"Pod {pod_name} - Succeeded")
                        status = ActivationStatus.COMPLETED
                        break

                    if event["object"].status.phase == "Failed":
                        pod_name = event["object"].metadata.name
                        LOGGER.info(f"Pod {pod_name} - Failed")

                        statuses = event["object"].status.container_statuses
                        if statuses and statuses[0]:
                            exit_code = statuses[0].state.terminated.exit_code
                            reason = statuses[0].state.terminated.reason
                            if exit_code in SUCCESSFUL_EXIT_CODES:
                                raise DeactivationException(
                                    f"Container exited with code {exit_code}"
                                )
                            else:
                                status = (ActivationStatus.FAILED,)
                                raise K8sActivationException(
                                    f"Container failed: {reason} with "
                                    f"exit code {exit_code}"
                                )
                        break

            except (
                DeactivationException,
                K8sActivationException,
            ):
                raise
            except ApiException as e:
                raise K8sActivationException(
                    f"Pod {self.pod_name} failed with error {e}"
                )
            finally:
                watcher.stop()
            LOGGER.info("Pod has started")
            return status

    def _set_namespace(self):
        ns_fileref = open(
            "/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r"
        )
        self.namespace = ns_fileref.read()
        LOGGER.info(f"Namespace is {self.namespace}")
        ns_fileref.close()

    def _wait_for_job_to_start(self) -> None:
        # Wait for job to be created
        while True:
            result = self.client.batch_api.list_namespaced_job(
                namespace=self.namespace,
                label_selector=f"job-name={self.job_name}",
                timeout_seconds=30,
            )

            if result.items:
                LOGGER.info("Job exists")
                break
            time.sleep(10)

        watcher = watch.Watch()
        while True:
            LOGGER.info("Still waiting for job to start")
            try:
                for event in watcher.stream(
                    self.client.batch_api.list_namespaced_job,
                    namespace=self.namespace,
                    label_selector=f"job-name={self.job_name}",
                    timeout_seconds=0,
                ):
                    o = event["object"]
                    obj_name = o.metadata.name

                    if o.status.succeeded:
                        LOGGER.info(f"Job {obj_name}: Succeeded")
                        break

                    if o.status.active:
                        LOGGER.info(f"Job {obj_name}: Active")
                        self._wait_for_pod_to_start()
                        break

                    if o.status.failed:
                        LOGGER.info(f"Job {obj_name}: Failed")
                        raise K8sActivationException(f"Job {obj_name}: Failed")

            except ApiException as e:
                raise K8sActivationException(f"Job {obj_name} Failed: \n {e}")
            finally:
                watcher.stop()

    def _create_secret(
        self,
        request: ContainerRequest,
    ) -> None:
        # Cleanup the secret before create it
        self._delete_secret()

        server = request.image_url.split("/")[0]
        cred_payload = {
            "auths": {
                server: {
                    "username": request.credential.username,
                    "password": request.credential.secret,
                }
            }
        }

        data = {
            ".dockerconfigjson": base64.b64encode(
                json.dumps(cred_payload).encode()
            ).decode()
        }

        secret = k8sclient.V1Secret(
            api_version="v1",
            data=data,
            kind="Secret",
            metadata={
                "name": self.secret_name,
                "namespace": self.namespace,
                "labels": {"aap": "eda"},
            },
            type="kubernetes.io/dockerconfigjson",
        )

        self.client.core_api.create_namespaced_secret(
            namespace=self.namespace,
            body=secret,
        )

        LOGGER.info(f"Created secret: name: {self.secret_name}")

    def _delete_secret(self) -> None:
        try:
            result = self.client.core_api.list_namespaced_secret(
                namespace=self.namespace,
                field_selector=f"metadata.name={self.secret_name}",
            )
            if not result.items:
                return

            result = self.client.core_api.delete_namespaced_secret(
                name=self.secret_name,
                namespace=self.namespace,
            )

            if result.status == "Success":
                LOGGER.info(f"Secret {self.secret_name} is deleted")
            else:
                LOGGER.error(
                    f"Failed to delete secret {self.secret_name}: ",
                    f"status: {result.status}",
                    f"reason: {result.reason}",
                )
        except ApiException as e:
            LOGGER.error(f"API Exception {e}")
            raise
