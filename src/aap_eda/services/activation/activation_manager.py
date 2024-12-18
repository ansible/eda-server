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
"""Module for Activation Manager."""
import contextlib
import logging
import typing as tp
from datetime import timedelta

import rq
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils import timezone
from pydantic import ValidationError

from aap_eda.api.serializers.activation import is_activation_valid
from aap_eda.core import models, tasking
from aap_eda.core.enums import ActivationStatus, RestartPolicy
from aap_eda.services.activation import exceptions
from aap_eda.services.activation.engine import exceptions as engine_exceptions
from aap_eda.services.activation.engine.common import ContainerRequest
from aap_eda.services.activation.restart_helper import (
    system_cancel_restart_activation,
    system_restart_activation,
)

from .db_log_handler import DBLogger
from .engine.common import ContainerableInvalidError, ContainerEngine
from .engine.factory import new_container_engine
from .status_manager import StatusManager, run_with_lock

LOGGER = logging.getLogger(__name__)


class ActivationManager(StatusManager):
    """Activation Manager manages the lifecycle of an activation.

    The Activation Manager is responsible for starting, stopping, restarting
    and monitoring an activation. It has a reference to the database instance
    and the container engine. It is also responsible for updating the status
    of the activation. It has mechanisms to prevent race conditions when
    updating the DB but only one instance of the manager for a given
    activation should be running at a time by async workers.
    """

    def __init__(
        self,
        db_instance: models.Activation,
        container_engine: tp.Optional[ContainerEngine] = None,
        container_logger_class: type[DBLogger] = DBLogger,
    ):
        """Initialize the Activation Manager.

        Args:
            db_instance: The database instance of the activation.
            container_engine: The container engine to use.
        """
        super().__init__(db_instance)
        if container_engine:
            self.container_engine = container_engine
        else:
            self.container_engine = new_container_engine(
                db_instance.id, self.db_instance_type
            )

        self.container_logger_class = container_logger_class

    def _update_started_time(self) -> None:
        """Update latest instance's started_at to now."""
        self.latest_instance.started_at = timezone.now()
        self.latest_instance.save(update_fields=["started_at"])

    def _set_activation_pod_id(self, pod_id: tp.Optional[str]) -> None:
        """Set the pod id of the activation instance."""
        # TODO: implement db locking?
        self.latest_instance.activation_pod_id = pod_id
        self.latest_instance.save(update_fields=["activation_pod_id"])

    @run_with_lock
    def _increase_failure_count(self):
        """Increase the failure count of the activation."""
        self.db_instance.failure_count += 1
        self.db_instance.save(update_fields=["failure_count", "modified_at"])

    @run_with_lock
    def _reset_failure_count(self):
        """Reset the failure count of the activation."""
        self.db_instance.failure_count = 0
        self.db_instance.save(update_fields=["failure_count", "modified_at"])

    @run_with_lock
    def _increase_restart_count(self):
        """Increase the restart count of the activation."""
        self.db_instance.restart_count += 1
        self.db_instance.save(update_fields=["restart_count", "modified_at"])

    @run_with_lock
    def _check_start_prerequirements(self) -> None:
        """Check if the activation can be started."""
        disallowed_statuses = [
            ActivationStatus.STARTING,
            ActivationStatus.DELETING,
        ]
        self.db_instance.refresh_from_db()

        if not self.db_instance.is_enabled:
            msg = (
                f"Activation {self.db_instance.id} is disabled. "
                "Can not be started."
            )
            LOGGER.warning(msg)
            raise exceptions.ActivationStartError(msg)

        if self.db_instance.status in disallowed_statuses:
            msg = (
                f"Activation {self.db_instance.id} is in "
                f"{self.db_instance.status} state, can not be started."
            )
            LOGGER.warning(msg)
            raise exceptions.ActivationStartError(msg)

        # serializator checks (dependent activation objects)
        is_valid, error = is_activation_valid(self.db_instance)
        if not is_valid:
            msg = (
                f"Activation {self.db_instance.id} can not be started. "
                f"Reason: {error}"
            )
            LOGGER.error(msg)
            self.set_status(ActivationStatus.ERROR, msg)
            raise exceptions.ActivationStartError(msg)

    def _check_latest_instance(self) -> None:
        """Check if the activation has a latest instance."""
        if not self.latest_instance:
            # how we want to handle this case?
            # for now we raise an error and let the monitor correct it
            msg = f"Activation {self.db_instance.id} has not instances."
            raise exceptions.ActivationInstanceNotFound(msg)

    def _check_latest_instance_and_pod_id(self) -> None:
        """Check if the activation has a latest instance and pod id."""
        self._check_latest_instance()

        if not self.latest_instance.activation_pod_id:
            # how we want to handle this case?
            # for now we raise an error and let the monitor correct it
            msg = f"Activation {self.db_instance.id} has not pod id."
            raise exceptions.ActivationInstancePodIdNotFound(msg)

    def _check_non_finalized_instances(self) -> None:
        args = {f"{self.db_instance_type}": self.db_instance}

        instances = models.RulebookProcess.objects.filter(**args)
        for instance in instances:
            if instance.status not in [
                ActivationStatus.STOPPED,
                ActivationStatus.COMPLETED,
                ActivationStatus.FAILED,
                ActivationStatus.ERROR,
            ]:
                msg = (
                    f"Activation {self.db_instance.id} has an unexpected "
                    f"instance {instance.id} in {instance.status} status. "
                    "Cleaning up the instance."
                )
                LOGGER.warning(msg)
                self._cleanup()
                self.set_latest_instance_status(ActivationStatus.STOPPED)
                self._set_activation_pod_id(pod_id=None)

    def _start_activation_instance(self):
        """Start a new activation instance.

        Update the status of the activation, latest instance, logs,
        counters and pod id.
        """
        self.set_status(ActivationStatus.STARTING)

        # Ensure status of previous instances
        # For consistency, we should not have previous instances in
        # wrong status. If we create a new instance, it means that
        # the previous instance should be previously managed.
        # This is a safety check.
        self._check_non_finalized_instances()

        # create a new instance
        LOGGER.info(
            "Creating a new activation instance for "
            f"activation: {self.db_instance.id}",
        )
        if not self.check_new_process_allowed():
            raise exceptions.MaxRunningProcessesError
        self._create_activation_instance()

        self.db_instance.refresh_from_db()
        log_handler = self.container_logger_class(self.latest_instance.id)

        LOGGER.info(
            "Starting container for activation instance: "
            f"{self.latest_instance.id}",
        )

        # start the container
        try:
            container_request = self._get_container_request()
            container_id = self.container_engine.start(
                container_request,
                log_handler,
            )
        except ValidationError as exc:
            msg = (
                f"Activation {self.db_instance.id} failed to start. "
                f"Reason: Container request is not valid."
                f"Errors: {exc.errors()}"
            )
            self._error_instance(msg)
            self._error_activation(msg)
            raise exceptions.ActivationStartError(msg) from exc
        except (
            engine_exceptions.ContainerImagePullError,
            engine_exceptions.ContainerLoginError,
        ) as exc:
            msg = (
                f"Activation {self.db_instance.id} failed to start. "
                f"Reason: {exc}"
            )
            self._failed_policy(msg)
            return
        except engine_exceptions.ContainerEngineError as exc:
            msg = (
                f"Activation {self.db_instance.id} failed to start. "
                f"Reason: {exc}"
            )
            self._error_instance(msg)
            self._error_activation(msg)
            raise exceptions.ActivationStartError(msg) from exc
        except Exception as exc:
            msg = (
                f"Activation {self.db_instance.id} failed to start "
                f"due to an un expected error. Msg: {exc}"
            )
            self._error_instance(msg)
            self._error_activation(msg)
            raise exceptions.ActivationStartError(msg) from exc

        self._set_activation_pod_id(pod_id=container_id)
        self._update_started_time()

        # update logs
        LOGGER.info(
            "Container start successful, "
            "updating logs for activation instance: "
            f"{self.latest_instance.id}",
        )

        self.update_logs()

    def _cleanup(self):
        """Cleanup the latest instance of the activation."""
        LOGGER.info(
            "Cleanup operation requested for activation id: "
            f"{self.db_instance.id}",
        )
        latest_instance = self.db_instance.latest_instance

        if not latest_instance or not latest_instance.activation_pod_id:
            LOGGER.info(
                f"Cleanup operation activation id: {self.db_instance.id} "
                "No instance or pod id found.",
            )
            return

        log_handler = self.container_logger_class(latest_instance.id)

        try:
            self.container_engine.cleanup(
                latest_instance.activation_pod_id,
                log_handler,
            )

        # We don't have identified cases where we want to stop the workflow
        # because of a cleanup error.
        # We are just logging the error and continue.
        except engine_exceptions.ContainerCleanupError as exc:
            pod_id = latest_instance.activation_pod_id
            msg = (
                f"Activation {self.db_instance.id} failed to cleanup its "
                f"latest instance {latest_instance.id} with pod id {pod_id}. "
                f"Reason: {exc}"
            )
            LOGGER.error(msg)
            log_handler.write(msg, flush=True)
            return

    def _is_in_status(self, status: ActivationStatus) -> bool:
        """Check if the activation is in a given status."""
        if self.db_instance.status != status:
            return False

        try:
            self._check_latest_instance_and_pod_id()
            pod_id = self.latest_instance.activation_pod_id
        except exceptions.ActivationInstancePodIdNotFound:
            pod_id = None

        container_status = None
        latest_instance = self.latest_instance

        if pod_id:
            with contextlib.suppress(engine_exceptions.ContainerNotFoundError):
                container_status = self.container_engine.get_status(
                    container_id=latest_instance.activation_pod_id,
                )

        if latest_instance.status != status:
            return False

        if latest_instance.status == status and (
            container_status is not None and container_status.status == status
        ):
            return True

        if latest_instance.status == status and (
            container_status is not None and container_status.status != status
        ):
            return False

        if (
            status != ActivationStatus.RUNNING
            and latest_instance.status == status
        ):
            return True

        return False

    def _is_already_running(self) -> bool:
        return self._is_in_status(ActivationStatus.RUNNING)

    def _is_already_stopped(self) -> bool:
        return (
            self._is_in_status(ActivationStatus.STOPPED)
            or self._is_in_status(ActivationStatus.COMPLETED)
            or self._is_in_status(ActivationStatus.FAILED)
            or self._is_in_status(ActivationStatus.ERROR)
        )

    def _is_unresponsive(self, check_readiness: bool) -> bool:
        previous_time = None
        if check_readiness:
            previous_time = self.latest_instance.started_at
            timeout = settings.RULEBOOK_READINESS_TIMEOUT_SECONDS
        elif self.db_instance.status in [
            ActivationStatus.RUNNING,
            ActivationStatus.STARTING,
        ]:
            previous_time = self.latest_instance.updated_at
            timeout = settings.RULEBOOK_LIVENESS_TIMEOUT_SECONDS

        if previous_time:
            cutoff_time = timezone.now() - timedelta(seconds=timeout)
            return previous_time < cutoff_time
        return False

    def _unresponsive_policy(self, check_type: str):
        """Apply the unresponsive restart policy."""
        LOGGER.info(
            "Unresponsive policy called for "
            f"activation id: {self.db_instance.id}",
        )
        container_logger = self.container_logger_class(self.latest_instance.id)
        if self.db_instance.restart_policy == RestartPolicy.NEVER:
            LOGGER.info(
                f"Activation id: {self.db_instance.id} "
                f"Restart policy is set to {self.db_instance.restart_policy}."
                "No restart policy is applied."
            )
            user_msg = (
                "Activation is unresponsive. "
                f"{check_type} check for ansible rulebook timed out. "
                "Restart policy is not applicable."
            )
            container_logger.write(user_msg, flush=True)
            self._fail_instance(user_msg)
            self.set_status(
                ActivationStatus.FAILED,
                user_msg,
            )

        else:
            LOGGER.info(
                f"Activation id: {self.db_instance.id} "
                f"Restart policy is set to {self.db_instance.restart_policy}."
                "Restart policy is applied.",
            )
            user_msg = (
                "Activation is unresponsive. "
                f"{check_type} check for ansible rulebook timed out. "
                "Activation is going to be restarted."
            )
            container_logger.write(user_msg, flush=True)
            self._fail_instance(msg=user_msg)
            self.set_status(
                ActivationStatus.FAILED,
                user_msg,
            )
            system_restart_activation(
                self.db_instance_type, self.db_instance.id, delay_seconds=1
            )

    def _missing_container_policy(self):
        LOGGER.info(
            "Missing container policy called for "
            f"activation id: {self.db_instance.id}",
        )
        container_logger = self.container_logger_class(self.latest_instance.id)
        msg = "Missing container for running activation."
        try:
            self._fail_instance(msg)
        except engine_exceptions.ContainerCleanupError as exc:
            msg = (
                f"Activation {self.db_instance.id} failed to cleanup. "
                f"Reason: {exc}"
            )
            LOGGER.error(msg)
            # Alex: Not sure if we want to change the status here.
            self.set_status(ActivationStatus.ERROR, msg)
            raise exceptions.ActivationMonitorError(msg) from exc

        if self.db_instance.restart_policy == RestartPolicy.NEVER:
            msg += " Restart policy not applicable."
        else:
            msg += " Restart policy is applied."
            system_restart_activation(
                self.db_instance_type, self.db_instance.id, delay_seconds=1
            )

        self.set_status(
            ActivationStatus.FAILED,
            msg,
        )
        container_logger.write(msg, flush=True)

    def _completed_policy(self, container_msg: str):
        """Apply the completed restart policy.

        Completed containers are only restart with ALWAYS policy.+
        """
        container_logger = self.container_logger_class(self.latest_instance.id)
        LOGGER.info(
            "Completed policy called for "
            f"activation id: {self.db_instance.id}",
        )

        if self.db_instance.restart_policy == RestartPolicy.ALWAYS:
            LOGGER.info(
                f"Activation id: {self.db_instance.id} "
                f"Restart policy is set to {self.db_instance.restart_policy}.",
            )
            user_msg = (
                f"Activation completed. It will attempt to restart in "
                f"{settings.ACTIVATION_RESTART_SECONDS_ON_COMPLETE} seconds "
                f"according to the restart policy {RestartPolicy.ALWAYS}."
                "It may take longer if there is no capacity available."
            )
            if container_msg:
                user_msg = f"{container_msg} {user_msg}"
            container_logger.write(user_msg, flush=True)
            self.set_latest_instance_status(
                ActivationStatus.COMPLETED,
                user_msg,
            )
            self.set_status(
                ActivationStatus.COMPLETED,
                user_msg,
            )
            system_restart_activation(
                self.db_instance_type,
                self.db_instance.id,
                delay_seconds=settings.ACTIVATION_RESTART_SECONDS_ON_COMPLETE,
            )
        else:
            LOGGER.info(
                f"Activation {self.db_instance.id} completed. "
                f"Restart policy is set to {self.db_instance.restart_policy}. "
                "No restart policy is applied.",
            )
            user_msg = (
                "Activation completed successfully. "
                "No restart policy is applied."
            )
            if container_msg:
                user_msg = f"{container_msg} {user_msg}"
            self.set_latest_instance_status(
                ActivationStatus.COMPLETED,
                user_msg,
            )
            self.set_status(
                ActivationStatus.COMPLETED,
                user_msg,
            )

    def _failed_policy(self, container_msg: str):
        container_logger = self.container_logger_class(self.latest_instance.id)
        """Apply the failed restart policy."""
        LOGGER.info(
            "Failed policy called for "
            f"activation id: {self.db_instance.id}",
        )

        # No restart if the restart policy is NEVER
        if self.db_instance.restart_policy == RestartPolicy.NEVER:
            LOGGER.info(
                f"Activation id: {self.db_instance.id} "
                f"Restart policy is set to {self.db_instance.restart_policy}.",
            )
            user_msg = "Activation failed. Restart policy is not applicable."
            if container_msg:
                user_msg = f"{container_msg} {user_msg}"
            container_logger.write(user_msg, flush=True)
            try:
                self._fail_instance(user_msg)
                self.set_status(
                    ActivationStatus.FAILED,
                    user_msg,
                )
            except engine_exceptions.ContainerCleanupError as exc:
                msg = (
                    f"Activation {self.db_instance.id} failed to cleanup. "
                    f"Reason: {exc}"
                )
                LOGGER.error(msg)
                # Alex: Not sure if we want to change the status here.
                self._error_instance(msg)
                self.set_status(ActivationStatus.ERROR, msg)
                raise exceptions.ActivationMonitorError(msg) from exc

        # No restart if it has reached the maximum number of restarts
        elif (
            self.db_instance.failure_count
            >= settings.ACTIVATION_MAX_RESTARTS_ON_FAILURE
        ):
            LOGGER.info(
                f"Activation id: {self.db_instance.id} "
                f"Restart policy is set to {self.db_instance.restart_policy}. "
                "Has reached the maximum number of restarts. ",
            )
            user_msg = (
                "Activation failed. "
                "Has reached the maximum number of restarts. "
                "Restart policy is not applicable."
            )
            if container_msg:
                user_msg = f"{container_msg} {user_msg}"
            container_logger.write(user_msg, flush=True)
            try:
                self._fail_instance(user_msg)
                self.set_status(
                    ActivationStatus.FAILED,
                    user_msg,
                )
            except engine_exceptions.ContainerCleanupError as exc:
                msg = (
                    f"Activation {self.db_instance.id} failed to cleanup. "
                    f"Reason: {exc}"
                )
                LOGGER.error(msg)
                # Alex: Not sure if we want to change the status here.
                self._error_instance(msg)
                self.set_status(ActivationStatus.ERROR, msg)
                raise exceptions.ActivationMonitorError(msg) from exc
        # Restart
        else:
            count_msg = (
                f"({self.db_instance.failure_count + 1}/"
                f"{settings.ACTIVATION_MAX_RESTARTS_ON_FAILURE})"
            )
            user_msg = (
                f"Activation failed. It will attempt to restart {count_msg} in"
                f" {settings.ACTIVATION_RESTART_SECONDS_ON_FAILURE} seconds "
                "according to the restart policy "
                f"{self.db_instance.restart_policy}."
                "It may take longer if there is no capacity available."
            )
            if container_msg:
                user_msg = f"{container_msg} {user_msg}"
            container_logger.write(user_msg, flush=True)
            try:
                self._fail_instance(user_msg)
                self.set_status(
                    ActivationStatus.FAILED,
                    user_msg,
                )
            except engine_exceptions.ContainerCleanupError as exc:
                msg = (
                    f"Activation {self.db_instance.id} failed to cleanup. "
                    f"Reason: {exc}"
                )
                LOGGER.error(msg)
                # Alex: Not sure if we want to change the status here.
                self.set_status(ActivationStatus.ERROR, msg)
                self.set_latest_instance_status(
                    ActivationStatus.ERROR,
                    msg,
                )
                raise exceptions.ActivationMonitorError(msg) from exc
            LOGGER.info(
                f"Activation {self.db_instance.id} failed. "
                f"Restart policy is set to {self.db_instance.restart_policy}. "
                f"Scheduling restart in "
                f"{settings.ACTIVATION_RESTART_SECONDS_ON_FAILURE} seconds.",
            )
            system_restart_activation(
                self.db_instance_type,
                self.db_instance.id,
                delay_seconds=settings.ACTIVATION_RESTART_SECONDS_ON_FAILURE,
            )

    def _fail_instance(self, msg: tp.Optional[str] = None):
        """Fail the latest activation instance."""
        kwargs = {}
        if msg:
            kwargs["status_message"] = msg
        self._cleanup()
        self.set_latest_instance_status(ActivationStatus.FAILED, **kwargs)
        self._set_activation_pod_id(pod_id=None)
        self._increase_failure_count()

    def _error_instance(self, msg: tp.Optional[str] = None):
        """Error the latest activation instance."""
        kwargs = {}
        if msg:
            kwargs["status_message"] = msg
        self._cleanup()
        self.set_latest_instance_status(ActivationStatus.ERROR, **kwargs)
        self._set_activation_pod_id(pod_id=None)

    def _stop_instance(self):
        """Stop the latest activation instance."""
        self.set_latest_instance_status(ActivationStatus.STOPPING)
        self._cleanup()
        self.set_latest_instance_status(ActivationStatus.STOPPED)
        self._set_activation_pod_id(pod_id=None)

    def _error_activation(self, msg: str):
        LOGGER.error(msg)
        self.set_status(ActivationStatus.ERROR, msg)

    def start(self, is_restart: bool = False):
        """Start an activation.

        Called by the user or by the monitor when the restart policy is applied
        Ensure that the activation meets all the requirements to start,
        otherwise raise ActivationStartError.
        Starts the activation in an idepotent way.
        """
        msg = f"Requested to start activation {self.db_instance.id}, starting."
        LOGGER.info(msg)

        try:
            self._check_start_prerequirements()
        except ObjectDoesNotExist:
            raise exceptions.ActivationStartError(
                "The Activation does not exist."
            )
        try:
            if self._is_already_running():
                msg = f"Activation {self.db_instance.id} is already running."
                LOGGER.info(msg)
                return
        except (
            exceptions.ActivationInstanceNotFound,
            exceptions.ActivationInstancePodIdNotFound,
        ):
            LOGGER.info(
                f"Start operation activation id: {self.db_instance.id} "
                "Expected activation instance or pod id but not found, "
                "recreating.",
            )

        self._start_activation_instance()
        if is_restart:
            self._increase_restart_count()

    def stop(self):
        """User requested stop."""
        LOGGER.info(
            "Stop operation requested for activation "
            f"id: {self.db_instance.id} Stopping activation.",
        )
        try:
            self.db_instance.refresh_from_db()
        except ObjectDoesNotExist:
            LOGGER.error(
                f"Stop operation failed: Activation {self.db_instance.id} "
                "does not exist.",
            )
            raise exceptions.ActivationStopError(
                "The Activation does not exist."
            ) from None
        try:
            self._check_latest_instance()
            if self._is_already_stopped():
                msg = f"Activation {self.db_instance.id} is already stopped."
                LOGGER.info(msg)
                return
        except exceptions.ActivationInstanceNotFound:
            LOGGER.info(
                f"Stop operation activation id: {self.db_instance.id} "
                "No instance found.",
            )
            self.set_status(ActivationStatus.STOPPED)
            return

        try:
            if self.db_instance.status != ActivationStatus.ERROR:
                self.set_status(ActivationStatus.STOPPING)
            self._stop_instance()

        except engine_exceptions.ContainerEngineError as exc:
            msg = (
                f"Activation {self.db_instance.id} failed to stop. "
                f"Reason: {exc}"
            )
            # Alex: Not sure if we want to change the status here.
            self._error_activation(msg)
            raise exceptions.ActivationStopError(msg) from exc
        user_msg = "Stop requested by user."
        if self.db_instance.status != ActivationStatus.ERROR:
            # do not overwrite the status and message if the activation
            # is already in error status
            self.set_status(ActivationStatus.STOPPED, user_msg)
        container_logger = self.container_logger_class(self.latest_instance.id)
        container_logger.write(user_msg, flush=True)
        LOGGER.info(
            f"Stop operation activation id: {self.db_instance.id} "
            "Activation stopped.",
        )

    def restart(self):
        """User requested restart."""
        container_logger = self.container_logger_class(self.latest_instance.id)

        LOGGER.info(
            "Restart operation requested for activation id: "
            "{self.db_instance.id} ",
        )
        self.stop()

        LOGGER.info(
            f"Activation manager activation id: {self.db_instance.id} "
            "Activation restart scheduled for 1 second.",
        )
        user_msg = "Restart requested by user. "
        self.set_status(ActivationStatus.PENDING, user_msg)
        container_logger.write(user_msg, flush=True)
        system_restart_activation(
            self.db_instance_type, self.db_instance.id, delay_seconds=1
        )

    def delete(self):
        """User requested delete."""
        LOGGER.info(
            f"Delete operation requested for activation id: "
            f"{self.db_instance.id},",
        )
        try:
            self._cleanup()

        # We catch all exceptions here to ensure that the activation is deleted
        except Exception as exc:
            msg = (
                f"Activation {self.db_instance.id} failed to cleanup. "
                f"Reason: {exc}"
            )
            LOGGER.error(msg)

        # Save the id; once the db instance is deleted the id is set to None.
        saved_id = self.db_instance.id
        try:
            self.db_instance.delete()
        except (ObjectDoesNotExist, ValueError):
            msg = (
                f"Delete operation failed: Activation {self.db_instance.id} "
                "does not exist."
            )
            LOGGER.error(msg)
            raise exceptions.ActivationManagerError(msg) from None

        # Cancel any outstanding restart.
        system_cancel_restart_activation(
            self.db_instance_type,
            saved_id,
        )

        LOGGER.info(
            f"Delete operation for activation id: {saved_id} "
            "Activation deleted.",
        )

    def monitor(self):
        """Monitor the activation.

        This method is intended to be run by an async worker triggered by
        the monitor scheduler. It is responsible for monitoring the activation
        and the latest activation instance. It checks the status of the
        container and ensures that the status of the activation and activation
        instance are consistent with the status of the container.

        Applies the restart policy if the container is in a restartable state.
        Updates the logs of the activation instance.

        TODO(alex): This method could be refactored.
        Restart policy may be moved to a separate class. We may need dependency
        injection if in the future we need to apply different policies.
        """
        LOGGER.info(
            "Monitor activation requested for  "
            f"activation id: {self.db_instance.id}",
        )

        # Ensure that the activation exists
        try:
            self.db_instance.refresh_from_db()
        except ObjectDoesNotExist:
            LOGGER.error(
                f"Monitor operation Failed: Activation {self.db_instance.id} "
                "does not exist.",
            )
            raise exceptions.ActivationMonitorError(
                f"Activation {self.db_instance.id} does not exist."
            )

        # Monitor expects that the activation has a latest instance
        # and a pod id
        try:
            self._check_latest_instance_and_pod_id()
        except exceptions.ActivationInstanceNotFound as e:
            LOGGER.error(f"Monitor operation Failed: {e}")
            self._error_activation(f"{e}")
            raise exceptions.ActivationMonitorError(f"{e}")
        except exceptions.ActivationInstancePodIdNotFound as e:
            LOGGER.error(f"Monitor operation Failed: {e}")
            self._error_activation(f"{e}")
            self._error_instance(f"{e}")
            raise exceptions.ActivationMonitorError(f"{e}")

        # Disabled activations should be stopped
        if not self.db_instance.is_enabled:
            LOGGER.info(
                f"Monitor operation: activation id: {self.db_instance.id} "
                "Activation is disabled. "
                "Applicable stop policy will be applied.",
            )
            self.stop()
            return

        if self.db_instance.status not in [
            ActivationStatus.STARTING,
            ActivationStatus.RUNNING,
            ActivationStatus.WORKERS_OFFLINE,
        ]:
            msg = (
                f"Monitor operation: activation id: {self.db_instance.id} "
                "Activation is not running. "
                "Nothing to do."
            )
            LOGGER.info(msg)
            return

        self._detect_running_status()

        # get the status of the container
        container_status = None
        try:
            container_status = self.container_engine.get_status(
                container_id=self.latest_instance.activation_pod_id,
            )
        except engine_exceptions.ContainerNotFoundError:
            pass
        except engine_exceptions.ContainerEngineError as exc:
            msg = (
                f"Monitor operation: activation id: {self.db_instance.id} "
                f"Failed to get status of the container. Reason: {exc}"
            )
            LOGGER.error(msg)
            self._error_instance(msg)
            self._error_activation(msg)
            raise exceptions.ActivationMonitorError(msg) from exc

        # Activations in running status must have a container
        # This case prevents cases when the container is externally deleted
        if container_status is None:
            self._missing_container_policy()
            return

        LOGGER.info(
            "Monitor operation: Current status of the instance for "
            f"the activation id {self.db_instance.id} "
            f"is {container_status}",
        )

        self.update_logs()

        if container_status.status == ActivationStatus.COMPLETED:  # RC == 0
            self._cleanup()
            self._completed_policy(container_status.message)
            return
        if container_status.status == ActivationStatus.FAILED:  # RC != 0
            self._cleanup()
            self._failed_policy(container_status.message)
            return

        # Detect unresponsive activation instance
        # TODO: we should decrease the default timeout/livecheck
        # in the future might be configurable per activation
        check_readiness = (
            self.latest_instance.status == ActivationStatus.STARTING
        )
        check_type = "Readiness" if check_readiness else "Liveness"
        if self._is_unresponsive(check_readiness=check_readiness):
            msg = (
                "Activation is unresponsive. "
                f"{check_type} check for ansible rulebook timed out. "
                "Applicable restart policy will be applied."
            )
            LOGGER.info(
                f"Monitor operation: activation id: {self.db_instance.id} "
                f"{msg}",
            )
            self._unresponsive_policy(check_type=check_type)
            return

        # last case is the success case
        if container_status.status == ActivationStatus.RUNNING:
            if self.db_instance.status == ActivationStatus.WORKERS_OFFLINE:
                LOGGER.info(
                    f"Monitor operation: activation id: {self.db_instance.id} "
                    "Activation is in WORKERS_OFFLINE state. "
                    "Setting activation and instance status to running.",
                )
                self.set_status(ActivationStatus.RUNNING)
                self.set_latest_instance_status(ActivationStatus.RUNNING)
            msg = (
                f"Monitor operation: activation id: {self.db_instance.id} "
                "Container is running. "
                "Updating logs."
            )
            LOGGER.info(msg)
            return

        # we don't expect an error status for the container
        # in these cases we run the cleanup and set the activation to error
        if container_status.status == ActivationStatus.ERROR:
            msg = (
                f"Monitor operation: activation id: {self.db_instance.id} "
                f"Container is in an error state. {container_status.message}"
            )
            LOGGER.error(msg)
            self._cleanup()
            self._error_instance(msg)
            self._error_activation(msg)
            raise exceptions.ActivationMonitorError(msg)

        # we don't expect stopping status for the container
        if container_status.status == ActivationStatus.STOPPED:
            raise exceptions.ActivationMonitorError(
                f"Container {self.latest_instance.activation_pod_id} "
                "is in an stopped state.",
            )

    def _detect_running_status(self):
        if (
            self.latest_instance.status == ActivationStatus.STARTING
            and self.latest_instance.updated_at
        ):
            # safely turn the status to running after updated_at was set
            # upon receiving at least one heartbeat
            with transaction.atomic():
                self.set_status(ActivationStatus.RUNNING)
                self.set_latest_instance_status(ActivationStatus.RUNNING)
                self._reset_failure_count()

    def update_logs(self):
        """Update the logs of the latest instance of the activation."""
        log_handler = self.container_logger_class(self.latest_instance.id)
        try:
            self._check_latest_instance_and_pod_id()
        except (
            exceptions.ActivationInstanceNotFound,
            exceptions.ActivationInstancePodIdNotFound,
        ):
            msg = (
                f"Update logs operation failed for activation id: "
                f"{self.db_instance.id} No instance or pod id found."
            )
            LOGGER.error(msg)
            # Alex: Not sure if we want to change the status here.
            # For now, we are not changing the status of the activation
            return

        try:
            self.container_engine.update_logs(
                container_id=self.latest_instance.activation_pod_id,
                log_handler=log_handler,
            )

        # We don't have identified cases where we want to stop the workflow
        # because of a log error.
        # We are just logging the error and continue.
        except engine_exceptions.ContainerEngineError as exc:
            msg = (
                f"Logs for activation {self.db_instance.id} could not be "
                f"fetch. Reason: {exc}"
            )
            LOGGER.error(msg)
            log_handler.write(msg, flush=True)
            # Alex: Not sure if we want to change the status here.
            # For now, we are not changing the status of the activation
            return

    @transaction.atomic
    def _create_activation_instance(self):
        git_hash = (
            self.db_instance.git_hash
            if hasattr(self.db_instance, "git_hash")
            else ""
        )
        args = {
            "name": self.db_instance.name,
            "status": ActivationStatus.STARTING,
            "git_hash": git_hash,
            "organization": self.db_instance.organization,
        }
        args[f"{self.db_instance_type}"] = self.db_instance
        try:
            rulebook_process = models.RulebookProcess.objects.create(**args)
        except IntegrityError as exc:
            msg = (
                f"Activation {self.db_instance.id} failed to create "
                f"activation instance. Reason: {exc}"
            )
            self._error_activation(msg)
            raise exceptions.ActivationStartError(msg) from exc
        queue_name = self._get_queue_name()
        models.RulebookProcessQueue.objects.create(
            process=rulebook_process,
            queue_name=queue_name,
        )

    @tasking.redis_connect_retry()
    def _get_queue_name(self) -> str:
        this_job = rq.get_current_job()
        return this_job.origin

    def _get_container_request(self) -> ContainerRequest:
        try:
            return self.db_instance.get_container_request()
        except ContainerableInvalidError:
            msg = (
                f"Activation {self.db_instance.id} not valid, "
                "container request cannot be built."
            )
            LOGGER.error(msg, exc_info=settings.DEBUG)
            raise exceptions.ActivationManagerError(msg)

    def check_new_process_allowed(self) -> bool:
        """Check if a new process is allowed."""
        if settings.MAX_RUNNING_ACTIVATIONS < 0:
            return True

        queue_name = self._get_queue_name()
        running_processes_count = models.RulebookProcess.objects.filter(
            status__in=[ActivationStatus.RUNNING, ActivationStatus.STARTING],
            rulebookprocessqueue__queue_name=queue_name,
        ).count()

        if running_processes_count >= settings.MAX_RUNNING_ACTIVATIONS:
            msg = (
                "No capacity to start a new rulebook process. "
                f"{self.db_instance_type} {self.db_instance.id} is postponed"
            )
            LOGGER.info(msg)
            self.set_status(ActivationStatus.PENDING, msg)
            return False
        return True
