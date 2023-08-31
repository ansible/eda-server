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
from enum import Enum

import yaml
from django.conf import settings
from django.db.utils import DatabaseError, IntegrityError
from django.utils import timezone

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus, RestartPolicy

from .activation_db_logger import ActivationDbLogger
from .activation_kubernetes import ActivationKubernetes
from .activation_podman import ActivationPodman
from .deactivation_podman import DeactivationPodman
from .exceptions import (
    ActivationException,
    ActivationRecordNotFound,
    DeactivationException,
)

logger = logging.getLogger(__name__)
ACTIVATION_PATH = "/api/eda/ws/ansible-rulebook"


class DeploymentType(Enum):
    PODMAN = "podman"
    K8S = "k8s"


# Move this to rulebook parser module
def find_ports(rulebook_text: str):
    """D401: Returns (host, port) pairs for all sources in a rulebook."""
    # Walk the rulebook and find ports in source parameters
    # Assume the rulebook is valid if it imported
    rulebook = yaml.safe_load(rulebook_text)

    # Make a list of host, port pairs found in all sources in
    # rulesets in a rulebook
    found_ports = []

    # Walk all rulesets in a rulebook
    for ruleset in rulebook:
        # Walk through all sources in a ruleset
        for source in ruleset.get("sources", []):
            # Remove name from source
            if "name" in source:
                del source["name"]
            # The first remaining key is the type and the arguments
            source_plugin = list(source.keys())[0]
            source_args = source[source_plugin]
            # Get host if it exists
            # Maybe check for "0.0.0.0" in the future
            host = source_args.get("host")
            # Get port if it exists
            maybe_port = source_args.get("port")
            # If port is an int we found a port to expose
            if isinstance(maybe_port, int):
                found_ports.append((host, maybe_port))

    return found_ports


def save_activation_and_instance(
    instance: models.ActivationInstance,
    update_fields: list,
):
    try:
        """
        Save instance and update the linked activation's
        status accordingly.
        """
        instance.activation.status = instance.status
        instance.activation.status_updated_at = timezone.now()
        running_states = [
            ActivationStatus.PENDING.value,
            ActivationStatus.STARTING.value,
            ActivationStatus.RUNNING.value,
            ActivationStatus.UNRESPONSIVE.value,
        ]
        activation_fields = ["status", "modified_at"]
        if str(instance.status) not in running_states:
            instance.activation.current_job_id = None
            activation_fields.append("current_job_id")
        if str(instance.status) == ActivationStatus.COMPLETED.value:
            instance.activation.failure_count = 0
            activation_fields.append("failure_count")

        instance.save(update_fields=update_fields)
        instance.activation.save(update_fields=activation_fields)
    except (IntegrityError, DatabaseError):
        message = f"Failed to update instance [id: {instance.id}]"
        logger.error(message)
        raise ActivationRecordNotFound(message)


class ActivateRulesets:
    def activate(self, activation: models.Activation) -> None:
        deployment_type = settings.DEPLOYMENT_TYPE
        ws_base_url = settings.WEBSOCKET_BASE_URL
        ssl_verify = settings.WEBSOCKET_SSL_VERIFY
        try:
            try:
                instance = models.ActivationInstance.objects.create(
                    activation=activation,
                    name=activation.name,
                    status=ActivationStatus.STARTING,
                    git_hash=activation.git_hash,
                )
            except IntegrityError:
                raise ActivationRecordNotFound(
                    f"Activation {activation.name} has been deleted."
                )

            activation_db_logger = ActivationDbLogger(instance.id)

            try:
                dtype = DeploymentType(deployment_type)
            except ValueError:
                instance.status = ActivationStatus.FAILED
                save_activation_and_instance(
                    instance=instance,
                    update_fields=["status", "ended_at", "updated_at"],
                )
                raise ActivationException(
                    f"Invalid deployment type: {deployment_type}"
                )

            ws_url = f"{ws_base_url}{ACTIVATION_PATH}"

            if dtype == DeploymentType.PODMAN:
                self.activate_in_podman(
                    ws_url=ws_url,
                    ssl_verify=ssl_verify,
                    activation_instance=instance,
                    decision_environment=activation.decision_environment,
                    activation_db_logger=activation_db_logger,
                )
            elif dtype == DeploymentType.K8S:
                logger.info(f"Activation DeploymentType: {dtype}")
                self.activate_in_k8s(
                    ws_url=ws_url,
                    ssl_verify=ssl_verify,
                    activation_instance=instance,
                    decision_environment=activation.decision_environment,
                )
            else:
                raise ActivationException(f"Unsupported {deployment_type}")

            if str(instance.status) == ActivationStatus.COMPLETED.value:
                self._log_activate_complete(
                    instance,
                    activation_db_logger,
                )
            elif str(instance.status) == ActivationStatus.FAILED.value:
                self._log_activate_failure(
                    ActivationException("Activation failed"),
                    instance,
                    activation_db_logger,
                )

            activation_db_logger.flush()

            now = timezone.now()
            instance.ended_at = now
            instance.updated_at = now
            save_activation_and_instance(
                instance=instance,
                update_fields=["status", "ended_at", "updated_at"],
            )
        except (DeactivationException, ActivationRecordNotFound) as error:
            logger.error(error)
        except Exception as error:
            logger.exception(f"Exception: {str(error)}")
            self._log_activate_failure(
                error,
                instance,
                activation_db_logger,
            )

    def deactivate(
        self,
        instance: models.ActivationInstance,
        final_status: ActivationStatus,
    ) -> None:
        try:
            deployment_type = settings.DEPLOYMENT_TYPE
            instance.status = ActivationStatus.STOPPING
            save_activation_and_instance(instance, ["status"])

            activation_db_logger = ActivationDbLogger(instance.id)
            try:
                dtype = DeploymentType(deployment_type)
            except ValueError:
                raise ActivationException(
                    f"Invalid deployment type: {deployment_type}"
                )

            if dtype == DeploymentType.PODMAN:
                self.deactivate_in_podman(
                    activation_instance=instance,
                    activation_db_logger=activation_db_logger,
                )
            elif dtype == DeploymentType.K8S:
                logger.info(f"Activation DeploymentType: {dtype}")
                self.deactivate_in_k8s(activation_instance=instance)
            else:
                raise ActivationException(f"Unsupported {deployment_type}")

            logger.info(
                f"Stopped Activation, Name: {instance.name}, ID: {instance.id}"
            )
            instance.status = final_status
            save_activation_and_instance(instance, ["status"])

        except Exception as exe:
            logger.exception(f"Activation error: {str(exe)}")
            activation_db_logger.write(f"Activation error: {str(exe)}")

    def _log_activate_complete(
        self,
        instance: models.ActivationInstance,
        activation_db_logger: ActivationDbLogger,
    ):
        restart_policy = (
            instance.activation.restart_policy == RestartPolicy.ALWAYS.value
        )
        if instance.activation.is_enabled and restart_policy:
            self._log_restart_activation(
                None,
                instance.activation,
                activation_db_logger,
            )

    def _log_activate_failure(
        self,
        error: Exception,
        instance: models.ActivationInstance,
        activation_db_logger: ActivationDbLogger,
    ):
        try:
            activation = instance.activation
            instance.status = ActivationStatus.FAILED
            restart_policy = (
                activation.restart_policy == RestartPolicy.ALWAYS.value
                or activation.restart_policy == RestartPolicy.ON_FAILURE.value
            )
            restart_limit = activation.failure_count < int(
                settings.ACTIVATION_MAX_RESTARTS_ON_FAILURE
            )
            if (
                activation.is_enabled
                and activation.is_valid
                and restart_policy
                and restart_limit
            ):
                self._log_restart_activation(
                    error,
                    activation,
                    activation_db_logger,
                    activation.failure_count + 1,
                    int(settings.ACTIVATION_MAX_RESTARTS_ON_FAILURE),
                )
                activation.failure_count += 1
                activation.save(update_fields=["failure_count", "modified_at"])
            else:
                more_reason = "unknown"
                if not restart_limit:
                    more_reason = (
                        "it has exceeds the maximum number of restarts"
                    )
                elif not restart_policy:
                    more_reason = "the restart policy is never"
                elif not activation.is_valid:
                    more_reason = "it is not restartable"
                msg = (
                    f"Activation {activation.name} failed: {str(error)}. "
                    f"Will not restart because {more_reason}"
                )
                logger.error(msg)
                activation_db_logger.write(msg)
        except (IntegrityError, DatabaseError):
            message = f"Failed to update instance [id: {instance.id}]"
            logger.error(message)
            raise ActivationRecordNotFound(message)

    def _log_restart_activation(
        self,
        error: Exception,
        activation: models.Activation,
        activation_db_logger: ActivationDbLogger,
        retry_count: int = 0,
        max_retries: int = 0,
    ) -> None:
        if error:
            seconds = int(settings.ACTIVATION_RESTART_SECONDS_ON_FAILURE)
            msg = (
                f"Activation {activation.name} failed: {str(error)}, "
                f"retry ({retry_count}/{max_retries}) in {seconds} seconds "
                "according to the activation's restart policy."
            )
            logger.warning(msg)
        else:
            seconds = int(settings.ACTIVATION_RESTART_SECONDS_ON_COMPLETE)
            msg = (
                f"Activation {activation.name} completed successfully. Will "
                f"restart in {seconds} seconds according to its restart policy"
            )
            logger.info(msg)

        activation_db_logger.write(msg)

    def activate_in_podman(
        self,
        ws_url: str,
        ssl_verify: str,
        activation_instance: models.ActivationInstance,
        decision_environment: models.DecisionEnvironment,
        activation_db_logger: ActivationDbLogger,
    ) -> None:
        podman = ActivationPodman(
            decision_environment,
            settings.PODMAN_SOCKET_URL,
            activation_db_logger,
        )

        ports = {}
        for _, port in find_ports(
            activation_instance.activation.rulebook_rulesets
        ):
            ports[f"{port}/tcp"] = port

        podman.run_worker_mode(
            ws_url=ws_url,
            ws_ssl_verify=ssl_verify,
            activation_instance=activation_instance,
            heartbeat=str(settings.RULEBOOK_LIVENESS_CHECK_SECONDS),
            ports=ports,
        )

    def deactivate_in_podman(
        self,
        activation_instance: models.ActivationInstance,
        activation_db_logger: ActivationDbLogger,
    ) -> None:
        if activation_instance.activation_pod_id is None:
            return

        podman = DeactivationPodman(
            settings.PODMAN_SOCKET_URL, activation_db_logger
        )
        podman.deactivate(activation_instance)

    def activate_in_k8s(
        self,
        ws_url: str,
        ssl_verify: str,
        activation_instance: models.ActivationInstance,
        decision_environment: models.DecisionEnvironment,
    ) -> None:
        activation = activation_instance.activation
        k8s = ActivationKubernetes()
        _pull_policy = "Always"

        ns_fileref = open(
            "/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r"
        )
        namespace = ns_fileref.read()
        ns_fileref.close()

        activation_id = activation.pk
        job_name = f"activation-job-{activation_id}"
        pod_name = f"activation-pod-{activation_id}"

        # build out container,pod,job specs
        container_spec = k8s.create_container(
            image=decision_environment.image_url,
            name=pod_name,
            pull_policy=_pull_policy,
            url=ws_url,
            ssl_verify=ssl_verify,
            activation_instance_id=activation_instance.id,
            ports=[
                port
                for _, port in find_ports(
                    activation_instance.activation.rulebook_rulesets
                )
            ],
            heartbeat=str(settings.RULEBOOK_LIVENESS_CHECK_SECONDS),
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

        for _, port in find_ports(
            activation_instance.activation.rulebook_rulesets
        ):
            k8s.create_service(
                namespace=namespace, job_name=job_name, port=port
            )

        # execute job
        k8s.run_activation_job(
            job_name=job_name,
            job_spec=job_spec,
            namespace=namespace,
            activation_instance=activation_instance,
            secret_name=secret_name,
        )
        activation_instance.activation.status = ActivationStatus.RUNNING
        save_activation_and_instance(activation_instance, ["status"])

    def deactivate_in_k8s(self, activation_instance) -> None:
        k8s = ActivationKubernetes()

        ns_fileref = open(
            "/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r"
        )
        namespace = ns_fileref.read()
        ns_fileref.close()

        logger.debug(f"namespace: {namespace}")
        logger.debug(f"activation_name: {activation_instance.name}")
        k8s.delete_job(activation_instance, namespace)
