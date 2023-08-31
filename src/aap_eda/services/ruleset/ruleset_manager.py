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

from django.conf import settings
from django.db.utils import DatabaseError, IntegrityError
from django.utils import timezone

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus, RestartPolicy

from .activation_db_logger import ActivationDbLogger
from .exceptions import (
    ActivationException,
    ActivationRecordNotFound,
    DeactivationException,
)
from .k8s_ruleset_handler import K8SRulesetHandler
from .podman_ruleset_handler import PodmanRulesetHandler
from .ruleset_handler import RulesetHandler

logger = logging.getLogger(__name__)


class DeploymentType(Enum):
    PODMAN = "podman"
    K8S = "k8s"


class RulesetManager:
    def __init__(self) -> None:
        self._handler = self._create_handler()

    @property
    def handler(self) -> RulesetHandler:
        return self._handler

    @handler.setter
    def handler(self, handler: RulesetHandler) -> None:
        self._handler = handler

    def activate(
        self,
        activation: models.Activation,
    ) -> None:
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

            self._handler.activate(
                instance=instance,
                activation_db_logger=activation_db_logger,
            )

            instance.refresh_from_db()
            if instance.status == ActivationStatus.COMPLETED:
                self._log_activate_complete(
                    instance,
                    activation_db_logger,
                )
            elif instance.status == ActivationStatus.FAILED:
                self._log_activate_failure(
                    ActivationException("Activation failed"),
                    instance,
                    activation_db_logger,
                )

            self._final_update(instance, activation_db_logger)
        except (
            DeactivationException,
            ActivationRecordNotFound,
            models.ActivationInstance.DoesNotExist,
        ) as error:
            logger.error(error)
        except Exception as error:
            logger.exception(f"Exception: {str(error)}")
            try:
                self._log_activate_failure(
                    error,
                    instance,
                    activation_db_logger,
                )
                self._final_update(instance, activation_db_logger)
            except ActivationRecordNotFound as error:
                logger.error(error)

    def deactivate(
        self,
        instance: models.ActivationInstance,
        final_status: ActivationStatus,
    ) -> None:
        try:
            instance.status = ActivationStatus.STOPPING
            instance.save(update_fields=["status"])

            activation_db_logger = ActivationDbLogger(instance.id)

            self._handler.deactivate(
                instance=instance,
                activation_db_logger=activation_db_logger,
            )

            logger.info(
                f"Stopped Activation, Name: {instance.name}, ID: {instance.id}"
            )
            instance.status = final_status
            self._handler.save_activation_and_instance(instance, ["status"])
        except Exception as exe:
            logger.exception(f"Activation error: {str(exe)}")
            activation_db_logger.write(f"Activation error: {str(exe)}")

    def _final_update(
        self,
        instance: models.ActivationInstance,
        activation_db_logger: ActivationDbLogger,
    ):
        activation_db_logger.flush()
        now = timezone.now()
        instance.ended_at = now
        instance.updated_at = now
        self._handler.save_activation_and_instance(
            instance=instance,
            update_fields=["status", "ended_at", "updated_at"],
        )

    def save_activation_and_instance(
        self,
        instance: models.ActivationInstance,
        update_fields: list,
    ):
        self._handler.save_activation_and_instance(
            instance=instance,
            update_fields=update_fields,
        )

    def _create_handler(self):
        deployment_type = settings.DEPLOYMENT_TYPE

        try:
            dtype = DeploymentType(deployment_type)
        except ValueError:
            raise ActivationException(
                f"Invalid deployment type: {deployment_type}"
            )

        if dtype == DeploymentType.PODMAN:
            return PodmanRulesetHandler()

        if dtype == DeploymentType.K8S:
            return K8SRulesetHandler()

    def _log_activate_complete(
        self,
        instance: models.ActivationInstance,
        activation_db_logger: ActivationDbLogger,
    ):
        restart_policy = (
            instance.activation.restart_policy == RestartPolicy.ALWAYS
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
                activation.restart_policy == RestartPolicy.ALWAYS
                or activation.restart_policy == RestartPolicy.ON_FAILURE
            )
            restart_limit = (
                activation.failure_count
                < settings.ACTIVATION_MAX_RESTARTS_ON_FAILURE
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
                    settings.ACTIVATION_MAX_RESTARTS_ON_FAILURE,
                )
                activation.failure_count += 1
                activation.save(update_fields=["failure_count", "modified_at"])
            else:
                more_reason = "unknown"
                if not activation.is_enabled:
                    more_reason = "activation is disabled"
                elif not restart_limit:
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
        except DatabaseError:
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
            seconds = settings.ACTIVATION_RESTART_SECONDS_ON_FAILURE
            msg = (
                f"Activation {activation.name} failed: {str(error)}, "
                f"retry ({retry_count}/{max_retries}) in {seconds} seconds "
                "according to the activation's restart policy."
            )
            logger.warning(msg)
        else:
            seconds = settings.ACTIVATION_RESTART_SECONDS_ON_COMPLETE
            msg = (
                f"Activation {activation.name} completed successfully. Will "
                f"restart in {seconds} seconds according to its restart policy"
            )
            logger.info(msg)
