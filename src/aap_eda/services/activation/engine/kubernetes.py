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
from dataclasses import dataclass
from datetime import datetime, timezone

from dateutil import parser
from kubernetes import client as k8sclient, config, watch
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException
from rest_framework import status

from aap_eda.core.enums import ActivationStatus
from aap_eda.services.activation.engine.exceptions import (
    ContainerCleanupError,
    ContainerEngineError,
    ContainerEngineInitError,
    ContainerImagePullError,
    ContainerNotFoundError,
    ContainerStartError,
    ContainerUpdateLogsError,
)

from . import messages
from .common import (
    ContainerEngine,
    ContainerRequest,
    ContainerStatus,
    LogHandler,
)

LOGGER = logging.getLogger(__name__)
KEEP_JOBS_FOR_SECONDS = 300

INVALID_IMAGE_NAME = "InvalidImageName"
IMAGE_PULL_BACK_OFF = "ImagePullBackOff"
IMAGE_PULL_ERROR = "ErrImagePull"

POD_FAILED_REASONS = [
    INVALID_IMAGE_NAME,
    IMAGE_PULL_BACK_OFF,
    IMAGE_PULL_ERROR,
]
POD_DELETE_TIMEOUT = 60


@dataclass
class Client:
    batch_api: k8sclient.BatchV1Api
    core_api: k8sclient.CoreV1Api
    network_api: k8sclient.NetworkingV1Api


def get_k8s_client() -> Client:
    """K8S client factory."""
    # Setup kubernetes api client
    try:
        config.load_incluster_config()

        return Client(
            batch_api=k8sclient.BatchV1Api(),
            core_api=k8sclient.CoreV1Api(),
            network_api=k8sclient.NetworkingV1Api(),
        )
    except ConfigException as e:
        raise ContainerEngineInitError(str(e)) from e


class Engine(ContainerEngine):
    def __init__(
        self,
        activation_id: str,
        resource_prefix: str,
        client=None,
    ) -> None:
        if client:
            self.client = client
        else:
            self.client = get_k8s_client()

        self._set_namespace()
        self.resource_prefix = resource_prefix.replace("_", "-")
        self.secret_name = f"{self.resource_prefix}-secret-{activation_id}"
        self.job_name = None
        self.pod_name = None

    def start(self, request: ContainerRequest, log_handler: LogHandler) -> str:
        # TODO : Should this be compatible with the previous version
        # Previous Version
        self.job_name = (
            f"{self.resource_prefix}-job-{request.process_parent_id}"
            f"-{request.rulebook_process_id}"
        )
        self.pod_name = (
            f"{self.resource_prefix}-pod-{request.process_parent_id}"
            f"-{request.rulebook_process_id}"
        )

        # Should we switch to new format
        # self.job_name = f"activation-job-" #noqa: E800
        # f"{request.id}-{uuid.uuid4()}" #noqa: E800
        try:
            log_handler.write("Creating Job")
            log_handler.write(f"Log tracking id: {request.log_tracking_id}")
            log_handler.write(f"Image URL is {request.image_url}", flush=True)
            self._create_job(request, log_handler)
            LOGGER.info("Waiting for pod to start")
            try:
                self._wait_for_pod_to_start(log_handler)
            except ContainerImagePullError as e:
                msg = messages.IMAGE_PULL_ERROR.format(
                    image_url=request.image_url,
                )
                raise ContainerImagePullError(msg) from e
            if request.ports:
                self._create_service(request)
            LOGGER.info(f"Job {self.job_name} is running")
            log_handler.write(f"Job {self.job_name} is running", flush=True)
            return self.job_name
        except ContainerEngineError as e:
            msg = (
                f"Failed to start job {self.job_name}, doing cleanup."
                f"Reason: {e}"
            )
            LOGGER.error(msg)
            log_handler.write(msg, flush=True)
            self.cleanup(self.job_name, log_handler)
            raise

    def get_status(self, container_id: str) -> ContainerStatus:
        pod = self._get_job_pod(container_id)

        container_status = pod.status.container_statuses[0]
        if container_status.state.running:
            message = messages.POD_RUNNING.format(
                pod_id=container_id,
            )
            status = ContainerStatus(
                status=ActivationStatus.RUNNING,
                message=message,
            )
        elif container_status.state.terminated:
            exit_code = container_status.state.terminated.exit_code
            if exit_code == 0:
                message = messages.POD_COMPLETED.format(
                    pod_id=container_id,
                )
                status = ContainerStatus(
                    status=ActivationStatus.COMPLETED,
                    message=message,
                )
                LOGGER.info(message)
            else:
                status = ContainerStatus(
                    status=ActivationStatus.FAILED,
                    message=container_status.state.terminated.message or "",
                )
                LOGGER.warning(
                    f"Pod exited with {exit_code}. Reason: "
                    f"{container_status.state.terminated.reason}"
                )
        else:
            LOGGER.error(
                "Pod is not running or terminated, "
                f"status: {container_status}"
                "set status to error.",
            )
            status = ContainerStatus(
                status=ActivationStatus.ERROR,
                message=container_status.state.waiting.message or "",
            )

        LOGGER.info(f"Job {container_id} status: {status}")
        return status

    def _get_ports(self, found_ports: list[tuple]) -> list[int]:
        return [port for _, port in found_ports]

    def cleanup(self, container_id: str, log_handler: LogHandler) -> None:
        self.job_name = container_id

        # These three methods raise ContainerCleanupError
        # handled by the manager
        self._delete_secret(log_handler)
        self._delete_services(log_handler)
        self._delete_job(log_handler)

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

                log_at = log_handler.get_log_read_at()

                if log_at:
                    current_dt = datetime.now(timezone.utc)

                    # 'since_seconds' can only accept integer of seconds
                    # read an extra second, the overlapped will be removed
                    log_args["since_seconds"] = (
                        current_dt - log_at
                    ).seconds + 1
                    log_handler.clear_log_write_from(int(log_at.timestamp()))

                log = self.client.core_api.read_namespaced_pod_log(**log_args)
                timestamp = None

                for line in log.splitlines():
                    timestamp, content = line.split(" ", 1)

                    # remove the overlapped lines
                    if log_at and log_at.timestamp() > self._set_log_timestamp(
                        timestamp
                    ):
                        continue

                    log_handler.write(
                        lines=content,
                        flush=False,
                        timestamp=False,
                        log_timestamp=self._set_log_timestamp(timestamp),
                    )

                if timestamp:
                    log_timestamp = self._set_log_timestamp(timestamp)
                    dt = datetime.fromtimestamp(
                        int(log_timestamp), timezone.utc  # remove millisecond
                    )
                    log_handler.flush()
                    log_handler.set_log_read_at(dt)
            else:
                msg = (
                    f"Pod with label {container_id} has unhandled state: "
                    f"{container_status.state}."
                )
                LOGGER.warning(msg)
                log_handler.write(msg, flush=True)

        # ContainerUpdateLogsError handled by the manager
        except ApiException as e:
            raise ContainerUpdateLogsError(str(e)) from e

    def _set_log_timestamp(self, log_timestamp: str) -> int:
        return int(parser.isoparse(log_timestamp).timestamp())

    def _get_job_pod(self, job_name: str) -> k8sclient.V1Pod:
        job_label = f"job-name={job_name}"
        try:
            result = self.client.core_api.list_namespaced_pod(
                namespace=self.namespace, label_selector=job_label
            )
            if not result.items:
                raise ContainerNotFoundError(
                    f"Pod with label {job_label} not found"
                )
            return result.items[0]
        except ApiException as e:
            LOGGER.error(f"API Exception {e}")
            raise ContainerNotFoundError(str(e)) from e

    def _create_container_spec(
        self,
        request: ContainerRequest,
        log_handler: LogHandler,
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
            f"args: {request.cmdline.get_args(sanitized=True)}"
        )

        log_handler.write(
            f"Container args {request.cmdline.get_args(sanitized=True)}", True
        )

        return container

    def _create_pod_template_spec(
        self,
        request: ContainerRequest,
        log_handler: LogHandler,
    ) -> k8sclient.V1PodTemplateSpec:
        container = self._create_container_spec(request, log_handler)
        if request.credential:
            self._create_secret(request, log_handler)
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
        return pod_template

    def _create_service(self, request: ContainerRequest) -> None:
        request_ports = [item[1] for item in request.ports]

        # only create the service if it does not already exist
        service_name = request.k8s_service_name

        try:
            service = self.client.core_api.list_namespaced_service(
                namespace=self.namespace,
                field_selector=f"metadata.name={service_name}",
            )

            if not service.items:
                LOGGER.info(f"Created request ports: {request_ports}")
                service_template = k8sclient.V1Service(
                    spec=k8sclient.V1ServiceSpec(
                        selector={
                            "app": "eda",
                            "job-name": self.job_name,
                        },
                        ports=[
                            k8sclient.V1ServicePort(
                                name=f"{service_name}-{port}",
                                protocol="TCP",
                                port=port,
                                target_port=port,
                            )
                            for port in request_ports
                        ],
                    ),
                    metadata=k8sclient.V1ObjectMeta(
                        name=f"{service_name}",
                        labels={
                            "app": "eda",
                            "job-name": self.job_name,
                            "created-by": "eda",
                        },
                        namespace=self.namespace,
                    ),
                )

                self.client.core_api.create_namespaced_service(
                    self.namespace, service_template
                )
                LOGGER.info(f"Created Service: {service_name}")
            else:
                LOGGER.warning(f"Service already exists: {service_name}")
                opened_ports = [
                    port_item.port for port_item in service.items[0].spec.ports
                ]
                if bool(set(request_ports) - set(opened_ports)):
                    raise ContainerStartError(
                        f"Request ports {request_ports} is not opened in the "
                        f"service {service_name} with ports: {opened_ports}"
                    )

        except ApiException as e:
            LOGGER.error(f"API Exception {e}")
            raise ContainerStartError(str(e)) from e

    def _delete_services(self, log_handler: LogHandler) -> None:
        try:
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
                log_handler.write(f"Service {service_name} is deleted.", True)
        except ApiException as e:
            LOGGER.error(f"API Exception {e}")
            raise ContainerCleanupError(str(e)) from e

    def _create_job(
        self,
        request: ContainerRequest,
        log_handler: LogHandler,
        backoff_limit=0,
        ttl=KEEP_JOBS_FOR_SECONDS,
    ) -> k8sclient.V1Job:
        pod_template = self._create_pod_template_spec(request, log_handler)

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

        try:
            job_result = self.client.batch_api.create_namespaced_job(
                namespace=self.namespace, body=job_spec
            )
            LOGGER.info(f"Submitted Job template: {self.job_name}")
        except ApiException as e:
            LOGGER.error(f"API Exception {e}")
            raise ContainerStartError(str(e)) from e

        return job_result

    def _delete_job(self, log_handler: LogHandler) -> None:
        try:
            activation_job = self.client.batch_api.list_namespaced_job(
                namespace=self.namespace,
                label_selector=f"job-name={self.job_name}",
                timeout_seconds=0,
            )

            if not (activation_job.items and activation_job.items[0].metadata):
                LOGGER.info(f"Job for {self.job_name} has been removed")
                return

            activation_job_name = activation_job.items[0].metadata.name
            self._delete_job_resource(activation_job_name, log_handler)

        except ApiException as e:
            raise ContainerCleanupError(
                f"Stop of {self.job_name} Failed: \n {e}"
            ) from e

    def _delete_job_resource(
        self, job_name: str, log_handler: LogHandler
    ) -> None:
        result = self.client.batch_api.delete_namespaced_job(
            name=job_name,
            namespace=self.namespace,
            propagation_policy="Background",
        )

        if result.status == "Failure":
            raise ContainerCleanupError(f"{result}")

        watcher = watch.Watch()
        try:
            for event in watcher.stream(
                self.client.core_api.list_namespaced_pod,
                namespace=self.namespace,
                label_selector=f"job-name={self.job_name}",
                timeout_seconds=POD_DELETE_TIMEOUT,
            ):
                if event["type"] == "DELETED":
                    log_handler.write(
                        f"Pod '{self.job_name}' is deleted.",
                        flush=True,
                    )
                    break

            log_handler.write(
                f"Job {self.job_name} is cleaned up.",
                flush=True,
            )
        except ApiException as e:
            if e.status == status.HTTP_404_NOT_FOUND:
                message = (
                    f"Pod '{self.job_name}' not found (404), "
                    "assuming it's already deleted."
                )
                log_handler.write(message, flush=True)
                return
            log_handler.write(
                f"Error while waiting for deletion: {e}", flush=True
            )
            raise ContainerCleanupError(
                f"Error during cleanup: {str(e)}"
            ) from e
        finally:
            watcher.stop()

    def _wait_for_pod_to_start(self, log_handler: LogHandler) -> None:
        watcher = watch.Watch()
        LOGGER.info("Waiting for pod to start")
        try:
            for event in watcher.stream(
                self.client.core_api.list_namespaced_pod,
                namespace=self.namespace,
                label_selector=f"job-name={self.job_name}",
            ):
                pod_name = event["object"].metadata.name
                pod_phase = event["object"].status.phase
                LOGGER.info(f"Pod {pod_name} - {pod_phase}")

                if pod_phase == "Pending":
                    statuses = event["object"].status.container_statuses

                    if statuses and statuses[0] and statuses[0].state.waiting:
                        message = statuses[0].state.waiting.message
                        reason = statuses[0].state.waiting.reason

                        if reason in POD_FAILED_REASONS:
                            raise ContainerImagePullError(message)

                if pod_phase in ["Failed", "Succeeded", "Running"]:
                    break
                if pod_phase == "Unknown":
                    error_msg = f"Pod {pod_name} has {pod_phase} status."
                    raise ContainerStartError(error_msg)
        except ApiException as e:
            raise ContainerStartError(
                f"Pod {self.pod_name} failed with error {e}"
            ) from e

        finally:
            watcher.stop()

    def _set_namespace(self) -> None:
        namespace_file = (
            "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
        )
        try:
            with open(
                namespace_file, mode="r", encoding="utf-8"
            ) as namespace_ref:
                self.namespace = namespace_ref.read()

            LOGGER.info(f"Namespace is {self.namespace}")
        except FileNotFoundError as e:
            message = f"Namespace file {namespace_file} does not exist."
            LOGGER.error(message)
            raise ContainerEngineInitError(message) from e

    def _create_secret(
        self,
        request: ContainerRequest,
        log_handler: LogHandler,
    ) -> None:
        # Cleanup the secret before create it
        self._delete_secret(log_handler)

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

        try:
            self.client.core_api.create_namespaced_secret(
                namespace=self.namespace,
                body=secret,
            )

            LOGGER.info(f"Created secret: name: {self.secret_name}")
        except ApiException as e:
            LOGGER.error(f"API Exception {e}")
            raise ContainerStartError(str(e)) from e

    def _delete_secret(self, log_handler: LogHandler) -> None:
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
                log_handler.write(
                    f"Secret {self.secret_name} is deleted.", True
                )
            else:
                message = (
                    f"Failed to delete secret {self.secret_name}: "
                    f"status: {result.status}"
                    f"reason: {result.reason}"
                )
                LOGGER.error(message)
                log_handler.write(message, True)
        except ApiException as e:
            LOGGER.error(f"API Exception {e}")
            raise ContainerCleanupError(str(e)) from e
