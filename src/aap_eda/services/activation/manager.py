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
import uuid
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils import timezone

from aap_eda.api.serializers.activation import is_activation_valid
from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus, RestartPolicy
from aap_eda.services.activation import exceptions
from aap_eda.services.activation.engine import exceptions as engine_exceptions
from aap_eda.services.activation.engine.common import (
    AnsibleRulebookCmdLine,
    ContainerRequest,
    Credential,
)

from .db_log_handler import DBLogger
from .engine.common import ContainerEngine
from .engine.factory import new_container_engine
from .engine.ports import find_ports

LOGGER = logging.getLogger(__name__)
ACTIVATION_PATH = "/api/eda/ws/ansible-rulebook"


class HasDbInstance(tp.Protocol):
    db_instance: tp.Any


def run_with_lock(func: tp.Callable) -> tp.Callable:
    """Run a method with a lock on the database instance."""

    @wraps(func)
    def _run_with_lock(self: HasDbInstance, *args, **kwargs):
        with transaction.atomic():
            locked_instance = (
                type(self.db_instance)
                .objects.select_for_update()
                .get(pk=self.db_instance.pk)
            )

            original_instance = self.db_instance
            self.db_instance = locked_instance

            try:
                return func(self, *args, **kwargs)
            finally:
                self.db_instance = original_instance
                self.db_instance.refresh_from_db()

    return _run_with_lock


class ActivationManager:
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
    ):
        """Initialize the Activation Manager.

        Args:
            db_instance: The database instance of the activation.
            container_engine: The container engine to use.
        """
        self.db_instance = db_instance
        if container_engine:
            self.container_engine = container_engine
        else:
            self.container_engine = new_container_engine(db_instance.id)

    @property
    def latest_instance(self) -> tp.Optional[models.ActivationInstance]:
        """Return the latest instance of the activation."""
        return self.db_instance.latest_instance

    def _set_activation_pod_id(self, pod_id: tp.Optional[str]) -> None:
        """Set the pod id of the activation instance."""
        # TODO: implement db locking?
        self.latest_instance.activation_pod_id = pod_id
        self.latest_instance.save(update_fields=["activation_pod_id"])

    def _set_latest_instance_status(
        self,
        status: ActivationStatus,
        status_message: tp.Optional[str] = None,
    ):
        """Set the status of the activation instance from the manager."""
        # TODO: implement db locking?
        kwargs = {"status": status}
        if status_message:
            kwargs["status_message"] = status_message
        self.latest_instance.update_status(**kwargs)

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
    def _set_activation_status(
        self,
        status: ActivationStatus,
        status_message: tp.Optional[str] = None,
    ) -> None:
        """Set the status from the manager."""
        kwargs = {"status": status}
        if status_message:
            kwargs["status_message"] = status_message
        self.db_instance.update_status(**kwargs)

    @run_with_lock
    def _check_start_prerequirements(self) -> None:
        """Check if the activation can be started."""

        disallowed_statuses = [
            ActivationStatus.STARTING,
            ActivationStatus.DELETING,
        ]
        self.db_instance.refresh_from_db

        if self.db_instance.is_enabled is False:
            msg = f"Activation {self.db_instance.id} is disabled. "
            "Can not be started."
            LOGGER.warning(msg)
            raise exceptions.ActivationStartError(msg)

        if self.db_instance.status in disallowed_statuses:
            msg = f"Activation {self.db_instance.id} is in "
            "f{self.db_instance.status} state, can not be started."
            LOGGER.warning(msg)
            raise exceptions.ActivationStartError(msg)

        # serializator checks (dependent activation objects)
        is_valid, error = is_activation_valid(self.db_instance)
        if not is_valid:
            msg = f"Activation {self.db_instance.id} can not be started. "
            f"Reason: {error}"
            LOGGER.error(msg)
            self._set_activation_status(ActivationStatus.ERROR, msg)
            raise exceptions.ActivationStartError(msg)

    def _check_latest_instance(self) -> None:
        """Check if the activation has a latest instance and pod id."""
        if not self.latest_instance:
            # how we want to handle this case?
            # for now we raise an error and let the monitor correct it
            msg = f"Activation {self.db_instance.id} has not instances."
            raise exceptions.ActivationInstanceNotFound(msg)

        if not self.latest_instance.activation_pod_id:
            # how we want to handle this case?
            # for now we raise an error and let the monitor correct it
            msg = f"Activation {self.db_instance.id} has not pod id."
            raise exceptions.ActivationInstancePodIdNotFound(msg)

    def _start_activation_instance(self):
        """Start a new activation instance.

        Update the status of the activation, latest instance, logs,
        counters and pod id.
        """
        self._set_activation_status(ActivationStatus.STARTING)

        # TODO(alex): long try block, we should be more specific
        try:
            LOGGER.info(
                "Creating a new activation instance for "
                f"activation: {self.db_instance.id}",
            )
            self._create_activation_instance()
            self.db_instance.refresh_from_db()
            self._set_latest_instance_status(ActivationStatus.STARTING)
            log_handler = DBLogger(self.latest_instance.id)

            LOGGER.info(
                "Starting container for activation instance: "
                f"{self.latest_instance.id}",
            )
            container_request = self._build_container_request()
            container_id = self.container_engine.start(
                container_request,
                log_handler,
            )

            # update status
            self._set_activation_status(ActivationStatus.RUNNING)
            self._set_latest_instance_status(ActivationStatus.RUNNING)
            self._set_activation_pod_id(pod_id=container_id)
            self._reset_failure_count()

            # update logs
            LOGGER.info(
                "Container start successful, "
                "updating logs for activation instance: "
                f"{self.latest_instance.id}",
            )
            self.container_engine.update_logs(container_id, log_handler)

        # note(alex): we may need to catch explicit exceptions
        # ContainerImagePullError might need to be handled differently
        # because it can be an error network and we might want to retry
        # so, activation should be in FAILED state to be handled by the monitor
        except engine_exceptions.ContainerEngineError as exc:
            msg = (
                f"Activation {self.db_instance.id} failed to start. "
                f"Reason: {exc}"
            )
            LOGGER.error(msg)
            self._set_activation_status(ActivationStatus.ERROR, msg)
            raise exceptions.ActivationStartError(msg) from exc

    def _cleanup(self):
        """Cleanup the latest instance of the activation."""
        # TODO: Catch exceptions from the engine as well as start method does
        self._set_activation_status(ActivationStatus.STOPPING)
        self._set_latest_instance_status(ActivationStatus.STOPPING)
        latest_instance = self.db_instance.latest_instance

        log_handler = DBLogger(latest_instance.id)
        self.container_engine.cleanup(
            latest_instance.activation_pod_id,
            log_handler,
        )

    def _is_in_status(self, status: ActivationStatus) -> bool:
        """Check if the activation is in a given status."""
        if self.db_instance.status == status:
            self._check_latest_instance()

            container_status = None
            latest_instance = self.latest_instance

            with contextlib.suppress(engine_exceptions.ContainerNotFoundError):
                container_status = self.container_engine.get_status(
                    container_id=latest_instance.activation_pod_id,
                )

            if latest_instance.status == status and (
                container_status is not None and container_status == status
            ):
                return True

            if latest_instance.status == status and (
                container_status is not None and container_status != status
            ):
                return False

            if latest_instance.status != status:
                return False

        return False

    def _is_already_running(self) -> bool:
        return self._is_in_status(ActivationStatus.RUNNING)

    def _is_already_stopped(self) -> bool:
        return self._is_in_status(ActivationStatus.STOPPED)

    def _is_unresponsive(self) -> bool:
        if self.db_instance.status in [
            ActivationStatus.RUNNING,
            ActivationStatus.STARTING,
        ]:
            cutoff_time = timezone.now() - timedelta(
                seconds=settings.RULEBOOK_LIVENESS_TIMEOUT_SECONDS,
            )
            return self.latest_instance.updated_at < cutoff_time
        return False

    def _unresponsive_policy(self):
        """Apply the unresponsive restart policy."""
        LOGGER.info(
            "Monitor operation: unresponsive mode called for "
            f"activation id: {self.activation_id}"
        )
        if self.db_instance.restart_policy == RestartPolicy.NEVER:
            LOGGER.info(
                f"Activation id: {self.db_instance.id} "
                f"Restart policy is set to {self.db_instance.restart_policy}.",
            )
            user_msg = (
                "Activation is unresponsive. "
                "Liveness check for ansible rulebook timed out. "
            )
            self._fail_instance(user_msg)
            self._set_activation_status(
                ActivationStatus.FAILED,
                user_msg,
            )

        else:
            LOGGER.info(
                f"Activation id: {self.db_instance.id} "
                f"Restart policy is set to {self.db_instance.restart_policy}.",
            )
            user_msg = (
                "Activation instance is unresponsive. "
                "Liveness check for ansible rulebook timed out. "
                "Restart policy is applied."
            )

            self._fail_instance(msg=user_msg)
            try:
                self.start(is_restart=True)
            except exceptions.ActivationStartError as exc:
                msg = (
                    f"Activation {self.db_instance.id} failed to start. "
                    f"Reason: {exc}"
                )
                LOGGER.error(msg)
                self._set_activation_status(ActivationStatus.ERROR, msg)
                raise exceptions.ActivationMonitorError(msg) from exc

    def _missing_container_policy(self):
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
            self._set_activation_status(ActivationStatus.ERROR, msg)
            raise exceptions.ActivationMonitorError(msg) from exc

        if self.db_instance.restart_policy == RestartPolicy.NEVER:
            msg += " Restart policy not applicable."
            self._set_activation_status(
                ActivationStatus.FAILED,
                msg,
            )
        else:
            try:
                self.start(is_restart=True)
            except exceptions.ActivationStartError as exc:
                msg = (
                    f"Activation {self.db_instance.id} failed to start. "
                    f"Reason: {exc}"
                )
                LOGGER.error(msg)
                self._set_activation_status(ActivationStatus.ERROR, msg)
                raise exceptions.ActivationMonitorError(msg) from exc

    def _completed_policy(self):
        """Apply the completed restart policy.

        Completed containers are only restart with ALWAYS policy.+
        """
        LOGGER.info(
            "Monitor operation: completed mode called for "
            f"activation id: {self.activation_id}",
        )

        if self.db_instance.restart_policy == RestartPolicy.ALWAYS:
            LOGGER.info(
                f"Activation id: {self.db_instance.id} "
                f"Restart policy is set to {self.db_instance.restart_policy}.",
            )
            user_msg = (
                "Activation completed successfully. Restart policy is applied."
            )
            self._set_latest_instance_status(
                ActivationStatus.COMPLETED,
                user_msg,
            )
            try:
                self._cleanup()
            except engine_exceptions.ContainerCleanupError as exc:
                msg = (
                    f"Activation {self.db_instance.id} failed to cleanup. "
                    f"Reason: {exc}"
                )
                LOGGER.error(msg)
                # Alex: Not sure if we want to set ERROR here.
                self._error_instance(msg)
                self._set_activation_status(ActivationStatus.ERROR, msg)
                raise exceptions.ActivationMonitorError(msg) from exc
            # TODO: schedule activation based on
            # ACTIVATION_RESTART_SECONDS_ON_COMPLETE
            # We should have a status like "pending restart"
            try:
                self.start()
            except exceptions.ActivationStartError as exc:
                msg = (
                    f"Activation {self.db_instance.id} failed to start. "
                    f"Reason: {exc}"
                )
                LOGGER.error(msg)
                raise exceptions.ActivationMonitorError(msg) from exc
        else:
            LOGGER.info(
                f"Activation id: {self.db_instance.id} "
                f"Restart policy is set to {self.db_instance.restart_policy}. "
                "No restart policy is applied.",
            )
            user_msg = (
                "Activation completed successfully. "
                "No restart policy is applied."
            )
            self._set_latest_instance_status(
                ActivationStatus.COMPLETED,
                user_msg,
            )
            try:
                self._cleanup()
            except engine_exceptions.ContainerCleanupError as exc:
                msg = (
                    f"Activation {self.db_instance.id} failed to cleanup. "
                    f"Reason: {exc}"
                )
                LOGGER.error(msg)
                # Alex: Not sure if we want to set ERROR here.
                self._error_instance(msg)
                self._set_activation_status(ActivationStatus.ERROR, msg)
                raise exceptions.ActivationMonitorError(msg) from exc

            user_msg = "Activation completed successfully."
            self._set_activation_status(
                ActivationStatus.COMPLETED,
                user_msg,
            )

    def _failed_policy(self):
        """Apply the failed restart policy."""
        LOGGER.info(
            "Monitor operation: failed mode called for "
            f"activation id: {self.activation_id}",
        )

        # No restart if the restart policy is NEVER
        if self.db_instance.restart_policy == RestartPolicy.NEVER:
            LOGGER.info(
                f"Activation id: {self.db_instance.id} "
                f"Restart policy is set to {self.db_instance.restart_policy}.",
            )
            user_msg = "Activation failed. Restart policy is not applicable."
            try:
                self._fail_instance(user_msg)
                self._set_activation_status(
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
                self._set_activation_status(ActivationStatus.ERROR, msg)
                raise exceptions.ActivationMonitorError(msg) from exc

        # No restart if it has reached the maximum number of restarts
        elif (
            self.db_instance.failure_count
            >= settings.ACTIVATION_MAX_RESTARTS_ON_FAILURE
        ):
            LOGGER.info(
                f"Activation id: {self.db_instance.id} "
                f"Restart policy is set to {self.db_instance.restart_policy}. ",
                "Has reached the maximum number of restarts. ",
            )
            user_msg = (
                "Activation failed. "
                "Has reached the maximum number of restarts. "
                "Restart policy is not applicable."
            )
            try:
                self._fail_instance(user_msg)
                self._set_activation_status(
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
                self._set_activation_status(ActivationStatus.ERROR, msg)
                raise exceptions.ActivationMonitorError(msg) from exc
        # Restart
        else:
            LOGGER.info(
                f"Activation id: {self.db_instance.id} "
                f"Restart policy is set to {self.db_instance.restart_policy}.",
            )
            user_msg = "Activation failed. Restart policy is applied."
            try:
                self._fail_instance(user_msg)
            except engine_exceptions.ContainerCleanupError as exc:
                msg = (
                    f"Activation {self.db_instance.id} failed to cleanup. "
                    f"Reason: {exc}"
                )
                LOGGER.error(msg)
                # Alex: Not sure if we want to change the status here.
                self._set_activation_status(ActivationStatus.ERROR, msg)
                self._set_latest_instance_status(
                    ActivationStatus.ERROR,
                    msg,
                )
                raise exceptions.ActivationMonitorError(msg) from exc
            try:
                # TODO: schedule activation based on ACTIVATION_RESTART_SECONDS_ON_FAILURE
                self.start(is_restart=True)
            except exceptions.ActivationStartError as exc:
                msg = (
                    f"Activation {self.db_instance.id} failed to start. "
                    f"Reason: {exc}"
                )
                LOGGER.error(msg)
                self._set_activation_status(ActivationStatus.ERROR, msg)
                raise exceptions.ActivationMonitorError(msg) from exc

    def _fail_instance(self, msg: tp.Optional[str] = None):
        """Fail the latest activation instance."""
        kwargs = {}
        if msg:
            kwargs["status_message"] = msg
        self._cleanup()
        self._set_latest_instance_status(ActivationStatus.FAILED, **kwargs)
        self._set_activation_pod_id(pod_id=None)
        self._increase_failure_count()

    def _error_instance(self, msg: tp.Optional[str] = None):
        """Error the latest activation instance."""
        kwargs = {}
        if msg:
            kwargs["status_message"] = msg
        self._cleanup()
        self._set_latest_instance_status(ActivationStatus.ERROR, **kwargs)
        self._set_activation_pod_id(pod_id=None)

    def _stop_instance(self):
        """Stop the latest activation instance."""
        self._cleanup()
        self._set_latest_instance_status(ActivationStatus.STOPPED)
        self._set_activation_pod_id(pod_id=None)

    def start(self, is_restart: bool = False):
        """Start an activation.

        Called by the user or by the monitor when the restart policy is applied.
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
        ) as exc:
            raise exceptions.ActivationStartError(str(exc)) from None

        # TODO: ensure previous instance status before starting a new one
        self._start_activation_instance()
        if is_restart:
            self._increase_restart_count()

    def stop(self):
        """User requested stop."""
        try:
            self.db_instance.refresh_from_db()
        except ObjectDoesNotExist:
            LOGGER.error(
                f"Stop operation Failed: Activation {self.db_instance.id} "
                "does not exist.",
            )
            raise exceptions.ActivationStartError(
                "The Activation does not exist."
            )
        LOGGER.info(
            f"Activation manager activation id: {self.db_instance.id} "
            "Stopping activation.",
        )
        try:
            self._check_latest_instance()
            if self._is_already_stopped():
                msg = f"Activation {self.db_instance.id} is already stopped."
                LOGGER.info(msg)
                self._set_activation_status(ActivationStatus.STOPPED)
                return
        except (
            exceptions.ActivationInstanceNotFound,
            exceptions.ActivationInstancePodIdNotFound,
        ):
            LOGGER.info(
                f"Stop operation activation id: {self.db_instance.id} "
                "No instance or pod id found.",
            )
            self._set_activation_status(ActivationStatus.STOPPED)
            return

        try:
            self._stop_instance()
            self._set_activation_status(ActivationStatus.STOPPED)
        except engine_exceptions.ContainerEngineError as exc:
            msg = (
                f"Activation {self.db_instance.id} failed to cleanup. "
                f"Reason: {exc}"
            )
            LOGGER.error(msg)
            # Alex: Not sure if we want to change the status here.
            self._set_activation_status(ActivationStatus.ERROR, msg)
            raise exceptions.ActivationStopError(msg) from exc
        LOGGER.info(
            f"Activation manager activation id: {self.db_instance.id} "
            "Activation stopped.",
        )

    def restart(self):
        """User requested restart."""
        LOGGER.info(
            f"Activation manager activation id: {self.db_instance.id} "
            "Restarting activation.",
        )
        self.stop()
        self.start(is_restart=True)
        LOGGER.info(
            f"Activation manager activation id: {self.db_instance.id} "
            "Activation restarted",
        )

    def delete(self):
        """User requested delete."""
        LOGGER.info(
            f"Activation manager activation id: {self.db_instance.id} "
            "Deleting activation.",
        )
        self.stop()
        self.db_instance.delete()
        LOGGER.info(
            f"Activation manager activation id: {self.db_instance.id} "
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
            "Activation manager monitoring "
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

        # Ensure that the activation instance exists
        try:
            self._check_latest_instance()
        except (
            exceptions.ActivationInstanceNotFound,
            exceptions.ActivationInstancePodIdNotFound,
        ) as e:
            LOGGER.error(f"Monitor operation Failed: {e}")
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

        if self.db_instance.status != ActivationStatus.RUNNING:
            msg = (
                f"Monitor operation: activation id: {self.db_instance.id} "
                "Activation is not running. "
                "Nothing to do."
            )
            LOGGER.info(msg)
            return

        # Detect unresponsive activation instance
        # TODO: we should decrease the default timeout/livecheck
        # in the future might be configurable per activation
        if self._is_unresponsive():
            msg = (
                "Activation is unresponsive. "
                "Liveness check for ansible rulebook timed out. "
                "Applicable restart policy will be applied."
            )
            LOGGER.info(
                f"Monitor operation: activation id: {self.db_instance.id} "
                f"{msg}",
            )
            self._unresponsive_policy()
            return

        # get the status of the container
        container_status = None
        with contextlib.suppress(engine_exceptions.ContainerNotFoundError):
            container_status = self.container_engine.get_status(
                container_id=self.latest_instance.activation_pod_id,
            )

        # Activations in running status must have a container
        # This case prevents cases when the container is externally deleted
        if container_status is None:
            self._missing_container_policy()
            return

        LOGGER.info(
            "Monitor operation: Current status of the instance for "
            f"the activation id {self.db_instance.id}"
            f"is {container_status}",
        )

        self.update_logs()
        # TODO: container status maybe should use its own dataclass
        if container_status == ActivationStatus.COMPLETED:  # RC == 0
            self._completed_policy()
            return
        if container_status == ActivationStatus.FAILED:  # RC != 0
            self._failed_policy()
            return

        if container_status == ActivationStatus.RUNNING:
            msg = (
                f"Monitor operation: activation id: {self.db_instance.id} "
                "Container is running. "
                "Updating logs."
            )
            return

        # we don't expect an error status for the container
        if container_status == ActivationStatus.ERROR:
            raise exceptions.ActivationMonitorError(
                f"Container {self.latest_instance.activation_pod_id} "
                "is in an error state."
            )

        # we don't expect stopping status for the container
        if container_status == ActivationStatus.STOPPED:
            raise exceptions.ActivationMonitorError(
                f"Container {self.latest_instance.activation_pod_id} "
                "is in an stopped state.",
            )

    def update_logs(self):
        """Update the logs of the latest instance of the activation."""
        log_handler = DBLogger(self.latest_instance.id)
        # TODO: check latest instance
        # TODO: catch exceptions from the engine
        self.container_engine.update_logs(
            container_id=self.latest_instance.activation_pod_id,
            log_handler=log_handler,
        )

    def _create_activation_instance(self):
        try:
            models.ActivationInstance.objects.create(
                activation=self.db_instance,
                name=self.db_instance.name,
                status=ActivationStatus.STARTING,
                git_hash=self.db_instance.git_hash,
            )
        except IntegrityError:
            raise exceptions.ActivationRecordNotFound(
                f"Activation {self.db_instance.name} has been deleted."
            )

    def _build_container_request(self) -> ContainerRequest:
        return ContainerRequest(
            credential=self._build_credential(),
            cmdline=self._build_cmdline(),
            name=f"eda-{self.latest_instance.id}-{uuid.uuid4()}",
            image_url=self.db_instance.decision_environment.image_url,
            ports=find_ports(self.db_instance.rulebook_rulesets),
            activation_id=self.db_instance.id,
            activation_instance_id=self.latest_instance.id,
        )

    def _build_credential(self) -> tp.Optional[Credential]:
        credential = self.db_instance.decision_environment.credential
        if credential:
            return Credential(
                username=credential.username,
                secret=credential.secret.get_secret_value(),
            )
        return None

    def _build_cmdline(self) -> AnsibleRulebookCmdLine:
        return AnsibleRulebookCmdLine(
            ws_url=settings.WEBSOCKET_BASE_URL + ACTIVATION_PATH,
            log_level=settings.ANSIBLE_RULEBOOK_LOG_LEVEL,
            ws_ssl_verify=settings.WEBSOCKET_SSL_VERIFY,
            heartbeat=settings.RULEBOOK_LIVENESS_CHECK_SECONDS,
            id=str(self.latest_instance.id),
        )
