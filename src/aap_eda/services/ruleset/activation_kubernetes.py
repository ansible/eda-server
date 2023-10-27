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
from django.db import DatabaseError
from django.utils import timezone
from kubernetes import client, config, watch
from kubernetes.client import exceptions

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.services.ruleset.exceptions import ActivationRecordNotFound, DeactivationException, K8sActivationException

from .shared_settings import VALID_LOG_LEVELS

logger = logging.getLogger(__name__)

GRACEFUL_TERM = 143


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
        activation_instance_id,
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
            str(activation_instance_id),
            "--heartbeat",
            str(heartbeat),
        ]
        if settings.ANSIBLE_RULEBOOK_LOG_LEVEL and settings.ANSIBLE_RULEBOOK_LOG_LEVEL in VALID_LOG_LEVELS:
            args.append(settings.ANSIBLE_RULEBOOK_LOG_LEVEL)

        container = client.V1Container(
            image=image,
            name=name,
            image_pull_policy=pull_policy,
            env=[client.V1EnvVar(name="ANSIBLE_LOCAL_TEMP", value="/tmp")],
            args=args,
            ports=[client.V1ContainerPort(container_port=port) for port in ports],
            command=["ansible-rulebook"],
        )

        logger.info(
            f"Created container: name: {container.name}, " f"image: {container.image} " f"args: {container.args}"
        )

        return container

    def create_secret(
        self,
        secret_name: str,
        namespace: str,
        decision_environment: models.DecisionEnvironment,
    ) -> None:
        # Cleanup the secret before create it
        self.delete_secret(secret_name, namespace)

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

        data = {".dockerconfigjson": base64.b64encode(json.dumps(cred_payload).encode()).decode()}

        secret = client.V1Secret(
            api_version="v1",
            data=data,
            kind="Secret",
            metadata={
                "name": secret_name,
                "namespace": namespace,
                "labels": {"aap": "eda"},
            },
            type="kubernetes.io/dockerconfigjson",
        )

        self.client_api.create_namespaced_secret(
            namespace=namespace,
            body=secret,
        )

        logger.info(f"Created secret: name: {secret_name}")

    @staticmethod
    def create_pod_template(pod_name, container, secret_name) -> client.V1PodTemplateSpec:
        if secret_name:
            spec = client.V1PodSpec(
                restart_policy="Never",
                containers=[container],
                image_pull_secrets=[client.V1LocalObjectReference(secret_name)],
            )
        else:
            spec = client.V1PodSpec(restart_policy="Never", containers=[container])

        pod_template = client.V1PodTemplateSpec(
            spec=spec,
            metadata=client.V1ObjectMeta(name=pod_name, labels={"app": "eda"}),
        )

        logger.info(f"Created Pod template: {pod_name}")

        return pod_template

    def create_service(self, job_name, port, namespace):
        # only create the service if it does not already exist
        service_name = f"{job_name}-{port}"

        service = self.client_api.list_namespaced_service(
            namespace=namespace, field_selector=f"metadata.name={service_name}"
        )

        if not service.items:
            service_template = client.V1Service(
                spec=client.V1ServiceSpec(
                    selector={"app": "eda", "job-name": job_name},
                    ports=[client.V1ServicePort(protocol="TCP", port=port, target_port=port)],
                ),
                metadata=client.V1ObjectMeta(
                    name=f"{service_name}",
                    labels={"app": "eda", "job-name": job_name},
                    namespace=namespace,
                ),
            )

            self.client_api.create_namespaced_service(namespace, service_template)
            logger.info(f"Created Service: {service_name}")
        else:
            logger.info(f"Service already exists: {service_name}")

    def delete_services(self, namespace, job_name) -> None:
        services = self.client_api.list_namespaced_service(namespace=namespace, label_selector=f"job-name={job_name}")

        for svc in services.items:
            service_name = svc.metadata.name

            self.client_api.delete_namespaced_service(
                name=service_name,
                namespace=namespace,
            )
            logger.info(f"Service {service_name} is deleted")

    @staticmethod
    def create_job(job_name, activation_id, pod_template, backoff_limit=0, ttl=0) -> client.V1Job:
        metadata = client.V1ObjectMeta(
            name=job_name,
            labels={
                "job-name": job_name,
                "app": "eda",
                "activation-id": str(activation_id),
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
                label_selector="activation-id=" f"{activation_instance.activation.pk}",
                timeout_seconds=0,
            )

            if activation_job.items and activation_job.items[0].metadata:
                activation_job_name = activation_job.items[0].metadata.name
                status = self.batch_api.delete_namespaced_job(
                    name=activation_job_name,
                    namespace=namespace,
                    propagation_policy="Background",
                )

                self.delete_services(
                    namespace=namespace,
                    job_name=activation_job_name,
                )

                secret_name = f"activation-secret-{activation_instance.activation.id}"
                self.delete_secret(
                    secret_name=secret_name,
                    namespace=namespace,
                )

                if status.status == "Failure":
                    raise K8sActivationException(f"{status}")
            else:
                logger.info(f"Job for : {instance_name} has been removed")

        except Exception as e:
            raise K8sActivationException(f"Stop {instance_name} Failed: \n {e}")

    def run_activation_job(
        self,
        job_name,
        job_spec,
        namespace,
        activation_instance,
        secret_name,
    ) -> None:
        # wait until old job instance has completely shut down.
        done = False
        while not done:
            if_job_exists = self.batch_api.list_namespaced_job(
                namespace=namespace,
                label_selector=f"job-name={job_name}",
                timeout_seconds=0,
            )

            if not if_job_exists.items:
                break

            time.sleep(10)

        logger.info(f"Create Job: {job_name}")
        job_result = self.batch_api.create_namespaced_job(namespace=namespace, body=job_spec)

        logger.info(f"Job Info: {job_result}")

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

            except DeactivationException:
                self.set_activation_status(
                    instance=activation_instance,
                    status=ActivationStatus.STOPPED,
                )
                raise
            except ActivationRecordNotFound as e:
                logger.error(e)
                raise
            except Exception as e:
                raise K8sActivationException(f"Job {obj_name} Failed: \n {e}")

            finally:
                # remove secret if created
                if secret_name:
                    self.delete_secret(
                        secret_name=secret_name,
                        namespace=namespace,
                    )
                    logger.info(f"Secret: {secret_name} is deleted.")
                # remove service(s) if created
                self.delete_services(
                    namespace=namespace,
                    job_name=job_name,
                )
                logger.info(f"Service: {job_name} is deleted.")

    def delete_secret(self, secret_name, namespace) -> None:
        try:
            ret = self.client_api.delete_namespaced_secret(
                name=secret_name,
                namespace=namespace,
            )

            if ret.status == "Success":
                logger.info(f"Secret {secret_name} is deleted")
            else:
                logger.error(
                    f"Failed to delete secret {secret_name}: ",
                    f"status: {ret.status}",
                    f"reason: {ret.reason}",
                )
        except exceptions.ApiException as e:
            if e.status == 404:
                logger.info(f"Secret {secret_name} not found")
            else:
                raise

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

        models.ActivationInstanceLog.objects.bulk_create(activation_instance_logs)
        logger.info(f"{line_number} of activation instance log are created.")

    def set_activation_status(self, instance: models.ActivationInstance, status: ActivationStatus) -> None:
        try:
            now = timezone.now()
            instance.status = status
            instance.updated_at = now
            instance.save(update_fields=["status", "updated_at"])

            update_fields = ["status", "modified_at", "status_updated_at"]
            activation = instance.activation
            activation.refresh_from_db()
            activation.status = status
            activation.status_updated_at = now
            if status == ActivationStatus.RUNNING and not activation.is_valid:
                activation.is_valid = True
                update_fields.append("is_valid")
            activation.save(update_fields=update_fields)
        except DatabaseError:
            message = f"Activation instance {instance.id} is not present."
            raise ActivationRecordNotFound(message)

    def watch_job_pod(self, job_name, namespace, activation_instance) -> None:
        w = watch.Watch()
        pod_failed_reasons = [
            "InvalidImageName",
            "ImagePullBackOff",
            "ErrImagePull",
        ]

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

                        statuses = event["object"].status.container_statuses

                        if statuses and statuses[0]:
                            logger.info(f"CONT STATUS: {statuses[0]}")

                            if statuses[0].state.waiting:
                                message = statuses[0].state.waiting.message
                                reason = statuses[0].state.waiting.reason
                                if reason in pod_failed_reasons:
                                    self.delete_job(activation_instance, namespace)
                                    self.set_activation_status(
                                        instance=activation_instance,
                                        status=ActivationStatus.FAILED,
                                    )
                                    raise K8sActivationException(message)

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

                        self.set_activation_status(
                            instance=activation_instance,
                            status=ActivationStatus.COMPLETED,
                        )
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

                        statuses = event["object"].status.container_statuses
                        if statuses and statuses[0]:
                            exit_code = statuses[0].state.terminated.exit_code
                            reason = statuses[0].state.terminated.reason
                            if exit_code == GRACEFUL_TERM:
                                # The stopped status is set in except block
                                raise DeactivationException(f"Container exited with code {exit_code}")
                            else:
                                self.set_activation_status(
                                    instance=activation_instance,
                                    status=ActivationStatus.FAILED,
                                )
                                raise K8sActivationException(
                                    f"Container failed: {reason} with " f"exit code {exit_code}"
                                )

                        done = True
            except (
                DeactivationException,
                ActivationRecordNotFound,
                K8sActivationException,
            ):
                raise
            except Exception as e:
                raise K8sActivationException(f"Pod {pod_name} failed with error {e}")

    def read_job_pod_log(self, pod_name, namespace, activation_instance_id) -> None:
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
                    # log info to DB
                    activation_instance_log = models.ActivationInstanceLog(
                        line_number=line_number,
                        log=line,
                        activation_instance_id=activation_instance_id,
                    )
                    activation_instance_log.save()

                    line_number += 1

                done = True
            except exceptions.ApiException as e:
                if e.status == 404:  # Not Found
                    raise DeactivationException(f"Failed to read logs of unavailable pod {pod_name}")
                else:
                    raise K8sActivationException(f"Failed to read pod logs: \n {e}")
            except DatabaseError:
                message = f"Instance [id: {activation_instance_id}] is not present."
                raise ActivationRecordNotFound(message)
            except Exception as e:
                raise K8sActivationException(f"Failed to read pod logs: \n {e}")
