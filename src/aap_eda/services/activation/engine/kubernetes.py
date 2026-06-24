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
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from dateutil import parser
from kubernetes import client as k8sclient, config, watch
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException
from rest_framework import status

from aap_eda.core.enums import ActivationStatus, ImagePullPolicy
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

K8S_API_RETRIES = 3
K8S_API_RETRY_BACKOFF = 1.0
K8S_API_TRANSIENT_STATUS_CODES = {401, 403, 500, 502, 503, 504}

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
        pod = self._get_job_pod(container_id)
        container_status = pod.status.container_statuses[0]
        if container_status.state.running or container_status.state.terminated:
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
                log_args["since_seconds"] = (current_dt - log_at).seconds + 1
                log_handler.clear_log_write_from(int(log_at.timestamp()))

            log = self._call_k8s_api(
                self.client.core_api.read_namespaced_pod_log,
                error_cls=ContainerUpdateLogsError,
                description=f"read pod log {container_id}",
                **log_args,
            )
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
                    int(log_timestamp),
                    timezone.utc,  # remove millisecond
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

    def _set_log_timestamp(self, log_timestamp: str) -> int:
        return int(parser.isoparse(log_timestamp).timestamp())

    def _refresh_client(self) -> None:
        """Re-read the SA token from disk and rebuild the K8s client."""
        try:
            self.client = get_k8s_client()
            LOGGER.info("Refreshed K8s client with new token from disk")
        except ContainerEngineInitError:
            LOGGER.warning("Failed to refresh K8s client, keeping old one")

    def _log_and_backoff(self, exc, attempt, description):
        """Log a transient K8s API error and back off before retry."""
        LOGGER.warning(
            "Transient K8s API error (HTTP %s) on attempt %d/%d for %s: %s",
            exc.status,
            attempt,
            K8S_API_RETRIES,
            description,
            exc.reason,
        )
        if attempt < K8S_API_RETRIES:
            time.sleep(K8S_API_RETRY_BACKOFF * attempt)
            if exc.status in {401, 403}:
                self._refresh_client()

    def _call_k8s_api(
        self,
        func,
        *args,
        error_cls=ContainerEngineError,
        description="K8s API call",
        **kwargs,
    ):
        """Call a K8s API function with retry on transient errors."""
        last_exc = None
        for attempt in range(1, K8S_API_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except ApiException as exc:
                last_exc = exc
                if exc.status not in K8S_API_TRANSIENT_STATUS_CODES:
                    raise error_cls(str(exc)) from exc
                self._log_and_backoff(exc, attempt, description)
        raise error_cls(
            f"{description} failed after "
            f"{K8S_API_RETRIES} retries: {last_exc}"
        ) from last_exc

    def _get_job_pod(self, job_name: str) -> k8sclient.V1Pod:
        job_label = f"job-name={job_name}"
        result = self._call_k8s_api(
            self.client.core_api.list_namespaced_pod,
            namespace=self.namespace,
            label_selector=job_label,
            description=f"pod lookup {job_label}",
        )
        if not result.items:
            raise ContainerNotFoundError(
                f"Pod with label {job_label} not found"
            )
        return result.items[0]

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
        limits: dict = {}
        if request.k8s_mem_limit:
            limits["memory"] = request.k8s_mem_limit
        if request.k8s_cpu_limit:
            limits["cpu"] = request.k8s_cpu_limit

        container = k8sclient.V1Container(
            image=request.image_url,
            name=request.name,
            image_pull_policy=ImagePullPolicy(request.pull_policy).to_k8s(),
            env=[k8sclient.V1EnvVar(name="ANSIBLE_LOCAL_TEMP", value="/tmp")],
            args=request.cmdline.get_args(),
            ports=ports,
            command=[request.cmdline.command()],
            resources=(
                k8sclient.V1ResourceRequirements(limits=limits)
                if limits
                else None
            ),
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
        pod_labels = {
            **(request.k8s_pod_labels or {}),
            "app": "eda",
            "job-name": self.job_name,
        }
        pod_meta = {
            "name": self.pod_name,
            "labels": pod_labels,
        }
        pod_annotations = request.k8s_pod_annotations or {}
        if pod_annotations:
            pod_meta["annotations"] = pod_annotations

        spec_kwargs: dict = {
            "restart_policy": "Never",
            "containers": [container],
        }
        if request.credential:
            self._create_secret(request, log_handler)
            spec_kwargs["image_pull_secrets"] = [
                k8sclient.V1LocalObjectReference(self.secret_name)
            ]
        sa_name = (request.k8s_pod_service_account_name or "").strip()
        if sa_name:
            spec_kwargs["service_account_name"] = sa_name
        node_selector = request.k8s_pod_node_selector or {}
        if node_selector:
            spec_kwargs["node_selector"] = node_selector

        tolerations = request.k8s_pod_tolerations or []
        if tolerations:
            spec_kwargs["tolerations"] = [
                k8sclient.V1Toleration(
                    key=t.get("key"),
                    operator=t.get("operator", "Equal"),
                    value=t.get("value"),
                    effect=t.get("effect"),
                    toleration_seconds=t.get("tolerationSeconds"),
                )
                for t in tolerations
            ]

        spec = k8sclient.V1PodSpec(**spec_kwargs)

        pod_template = k8sclient.V1PodTemplateSpec(
            spec=spec,
            metadata=k8sclient.V1ObjectMeta(**pod_meta),
        )

        LOGGER.info(f"Created Pod template: {self.pod_name}")
        return pod_template

    def _create_service(self, request: ContainerRequest) -> None:
        request_ports = [item[1] for item in request.ports]

        # only create the service if it does not already exist
        service_name = request.k8s_service_name

        service = self._call_k8s_api(
            self.client.core_api.list_namespaced_service,
            namespace=self.namespace,
            field_selector=f"metadata.name={service_name}",
            error_cls=ContainerStartError,
            description=f"list service {service_name}",
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

            self._call_k8s_api(
                self.client.core_api.create_namespaced_service,
                self.namespace,
                service_template,
                error_cls=ContainerStartError,
                description=f"create service {service_name}",
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

    def _delete_services(self, log_handler: LogHandler) -> None:
        services = self._call_k8s_api(
            self.client.core_api.list_namespaced_service,
            namespace=self.namespace,
            label_selector=f"job-name={self.job_name}",
            error_cls=ContainerCleanupError,
            description=f"list services for {self.job_name}",
        )

        for svc in services.items or []:
            service_name = svc.metadata.name
            self._call_k8s_api(
                self.client.core_api.delete_namespaced_service,
                name=service_name,
                namespace=self.namespace,
                error_cls=ContainerCleanupError,
                description=f"delete service {service_name}",
            )
            LOGGER.info(f"Service {service_name} is deleted")
            log_handler.write(f"Service {service_name} is deleted.", True)

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

        job_result = self._call_k8s_api(
            self.client.batch_api.create_namespaced_job,
            namespace=self.namespace,
            body=job_spec,
            error_cls=ContainerStartError,
            description=f"create job {self.job_name}",
        )
        LOGGER.info(f"Submitted Job template: {self.job_name}")

        return job_result

    def _delete_job(self, log_handler: LogHandler) -> None:
        activation_job = self._call_k8s_api(
            self.client.batch_api.list_namespaced_job,
            namespace=self.namespace,
            label_selector=f"job-name={self.job_name}",
            timeout_seconds=0,
            error_cls=ContainerCleanupError,
            description=f"list job {self.job_name}",
        )

        if not (activation_job.items and activation_job.items[0].metadata):
            LOGGER.info(f"Job for {self.job_name} has been removed")
            return

        activation_job_name = activation_job.items[0].metadata.name
        self._delete_job_resource(activation_job_name, log_handler)

    def _delete_job_resource(
        self, job_name: str, log_handler: LogHandler
    ) -> None:
        result = self._call_k8s_api(
            self.client.batch_api.delete_namespaced_job,
            name=job_name,
            namespace=self.namespace,
            propagation_policy="Background",
            error_cls=ContainerCleanupError,
            description=f"delete job {job_name}",
        )

        if result.status == "Failure":
            raise ContainerCleanupError(f"{result}")

        self._watch_pod_deletion(log_handler)

    def _watch_pod_deletion(self, log_handler: LogHandler) -> None:
        """Watch for pod deletion with retry on transient errors."""
        desc = f"watch pod deletion {self.job_name}"
        last_exc = None
        for attempt in range(1, K8S_API_RETRIES + 1):
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
                return
            except ApiException as exc:
                last_exc = exc
                if exc.status == status.HTTP_404_NOT_FOUND:
                    msg = (
                        f"Pod '{self.job_name}' not found (404), "
                        "assuming it's already deleted."
                    )
                    log_handler.write(msg, flush=True)
                    return
                if exc.status not in K8S_API_TRANSIENT_STATUS_CODES:
                    log_handler.write(
                        f"Error while waiting for deletion: {exc}",
                        flush=True,
                    )
                    raise ContainerCleanupError(
                        f"Error during cleanup: {str(exc)}"
                    ) from exc
                self._log_and_backoff(exc, attempt, desc)
            finally:
                watcher.stop()
        raise ContainerCleanupError(
            f"{desc} failed after {K8S_API_RETRIES} retries: {last_exc}"
        ) from last_exc

    def _process_pod_start_event(self, event) -> bool:
        """Process a pod watch event during startup.

        Returns True when the pod has reached a terminal-for-startup
        phase (Running, Succeeded, Failed) and the caller should stop
        watching.  Raises on image-pull or unknown-phase errors.
        """
        pod_name = event["object"].metadata.name
        pod_phase = event["object"].status.phase
        LOGGER.info(f"Pod {pod_name} - {pod_phase}")

        if pod_phase == "Pending":
            statuses = event["object"].status.container_statuses
            if statuses and statuses[0] and statuses[0].state.waiting:
                reason = statuses[0].state.waiting.reason
                if reason in POD_FAILED_REASONS:
                    message = statuses[0].state.waiting.message
                    raise ContainerImagePullError(message)
            return False

        if pod_phase in ["Failed", "Succeeded", "Running"]:
            return True

        if pod_phase == "Unknown":
            raise ContainerStartError(
                f"Pod {pod_name} has {pod_phase} status."
            )
        return False

    def _wait_for_pod_to_start(self, log_handler: LogHandler) -> None:
        """Wait for the pod to reach a running state."""
        LOGGER.info("Waiting for pod to start")
        desc = f"watch pod start {self.job_name}"
        last_exc = None
        for attempt in range(1, K8S_API_RETRIES + 1):
            watcher = watch.Watch()
            try:
                for event in watcher.stream(
                    self.client.core_api.list_namespaced_pod,
                    namespace=self.namespace,
                    label_selector=f"job-name={self.job_name}",
                ):
                    if self._process_pod_start_event(event):
                        return
            except ApiException as exc:
                last_exc = exc
                if exc.status not in K8S_API_TRANSIENT_STATUS_CODES:
                    raise ContainerStartError(
                        f"Pod {self.pod_name} failed with error {exc}"
                    ) from exc
                self._log_and_backoff(exc, attempt, desc)
            finally:
                watcher.stop()
        raise ContainerStartError(
            f"{desc} failed after {K8S_API_RETRIES} retries: {last_exc}"
        ) from last_exc

    def _set_namespace(self) -> None:
        ns_override = os.environ.get("EDA_ACTIVATION_JOB_NAMESPACE", "")
        if ns_override.strip():
            self.namespace = ns_override.strip()
            LOGGER.info(
                "Using activation job namespace override: %s",
                self.namespace,
            )
            return

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

        self._call_k8s_api(
            self.client.core_api.create_namespaced_secret,
            namespace=self.namespace,
            body=secret,
            error_cls=ContainerStartError,
            description=f"create secret {self.secret_name}",
        )
        LOGGER.info(f"Created secret: name: {self.secret_name}")

    def _delete_secret(self, log_handler: LogHandler) -> None:
        result = self._call_k8s_api(
            self.client.core_api.list_namespaced_secret,
            namespace=self.namespace,
            field_selector=f"metadata.name={self.secret_name}",
            error_cls=ContainerCleanupError,
            description=f"list secret {self.secret_name}",
        )
        if not result.items:
            return

        result = self._call_k8s_api(
            self.client.core_api.delete_namespaced_secret,
            name=self.secret_name,
            namespace=self.namespace,
            error_cls=ContainerCleanupError,
            description=f"delete secret {self.secret_name}",
        )

        if result.status == "Success":
            LOGGER.info(f"Secret {self.secret_name} is deleted")
            log_handler.write(f"Secret {self.secret_name} is deleted.", True)
        else:
            message = (
                f"Failed to delete secret {self.secret_name}: "
                f"status: {result.status}"
                f"reason: {result.reason}"
            )
            LOGGER.error(message)
            log_handler.write(message, True)
