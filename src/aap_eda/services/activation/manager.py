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
from functools import wraps

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.utils import IntegrityError

from aap_eda.api.serializers.activation import is_activation_valid
from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
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
        container_engine: ContainerEngine = None,
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

    @run_with_lock
    def _set_activation_pod_id(self, pod_id: tp.Optional[str]) -> None:
        """Set the pod id of the activation instance."""
        self.latest_instance.activation_pod_id = pod_id
        self.latest_instance.save(update_fields=["activation_pod_id"])

    @run_with_lock
    def _set_activation_status(
        self,
        status: ActivationStatus,
        status_message: tp.Optional[str] = None,
    ):
        """Set the status from the manager with locking."""
        kwargs = {"status": status}
        if status_message:
            kwargs["status_message"] = status_message
        self.db_instance.update_status(**kwargs)

    @run_with_lock
    def _set_activation_instance_status(
        self,
        status: ActivationStatus,
        status_message: tp.Optional[str] = None,
    ):
        """Set the status from the manager with locking."""
        kwargs = {"status": status}
        if status_message:
            kwargs["status_message"] = status_message
        self.latest_instance.update_status(**kwargs)

    @run_with_lock
    def _check_stop_prerequirements(self):
        """Check if the activation can be stopped."""

        disallowed_statuses = [
            ActivationStatus.STOPPING,
            ActivationStatus.DELETING,
        ]
        self.db_instance.refresh_from_db

        if self.db_instance.is_enabled is False:
            msg = f"Activation {self.db_instance.id} is disabled. "
            f"Can not be stopped."
            LOGGER.warning(msg)
            raise exceptions.ActivationStopError(msg)

        if self.db_instance.status in disallowed_statuses:
            msg = f"Activation {self.db_instance.id} is in "
            f"{self.db_instance.status} state, can not be stopped."
            LOGGER.warning(msg)
            raise exceptions.ActivationStopError(msg)

    @run_with_lock
    def _check_start_prerequirements(self):
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

    def _check_latest_instance(self):
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
        self._set_activation_status(ActivationStatus.STARTING)

        # TODO(alex): long try block, we should be more specific
        try:
            LOGGER.info(
                "Creating a new activation instance for "
                f"activation: {self.db_instance.id}",
            )
            self._create_activation_instance()
            self.db_instance.refresh_from_db()
            self._set_activation_instance_status(ActivationStatus.STARTING)
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
            self._set_activation_instance_status(ActivationStatus.RUNNING)
            self._set_activation_pod_id(pod_id=container_id)

            # update logs
            LOGGER.info(
                "Container start successful. "
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

    def _stop_latest_instance(self):
        # TODO: Catch exceptions from the engine as well as start method does
        self._set_activation_status(ActivationStatus.STOPPING)
        self._set_activation_instance_status(ActivationStatus.STOPPING)
        latest_instance = self.db_instance.latest_instance

        log_handler = DBLogger(latest_instance.id)
        self.container_engine.cleanup(
            latest_instance.activation_pod_id,
            log_handler,
        )
        self._set_activation_status(ActivationStatus.STOPPED)
        self._set_activation_instance_status(ActivationStatus.STOPPED)
        self._set_activation_pod_id(pod_id=None)

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

    def start(self):
        """Start an activation.

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
        self._start_activation_instance()

    def stop(self):
        try:
            self._check_stop_prerequirements()
        except ObjectDoesNotExist:
            raise exceptions.ActivationStartError(
                "The Activation does not exist."
            )
        try:
            self._check_latest_instance()
            if self._is_already_stopped():
                msg = f"Activation {self.db_instance.id} is already stopped."
                LOGGER.info(msg)
                return
        except (
            exceptions.ActivationInstanceNotFound,
            exceptions.ActivationInstancePodIdNotFound,
        ) as exc:
            raise exceptions.ActivationStopError(str(exc)) from None
        self._stop_latest_instance()

    def restart(self):
        self.stop()
        self.start()

    def monitor(self):
        # TODO: we should check if the db_instance is good
        LOGGER.info(f"Monitoring activation id: {self.db_instance.id}")
        try:
            self._check_latest_instance()
        except (
            exceptions.ActivationInstanceNotFound,
            exceptions.ActivationInstancePodIdNotFound,
        ) as e:
            LOGGER.error(f"Monitor operation Failed: {e}")
            raise exceptions.ActivationMonitorError(f"{e}")

        log_handler = DBLogger(self.latest_instance.id)
        # TODO: long try block, we should be more specific
        try:
            container_status = self.container_engine.get_status(
                self.latest_instance.activation_pod_id
            )
            LOGGER.info(
                f"Current status of instance {self.latest_instance.id} "
                f"is {container_status}",
            )
            # TODO: implement restart policy logic
            if container_status in [
                ActivationStatus.COMPLETED,
                ActivationStatus.FAILED,
                ActivationStatus.STOPPED,
            ]:
                # TODO: it should be the cleanup method
                # stop is implicit in the cleanup method
                # stop is not clear that it performs a cleanup
                # but there is not any stop without cleanup
                self.container_engine.cleanup(
                    self.latest_instance.activation_pod_id,
                    log_handler,
                )
                self._set_activation_status(container_status)
                self._set_activation_instance_status(container_status)
                self._set_activation_pod_id(pod_id=None)
            elif container_status == ActivationStatus.RUNNING:
                LOGGER.info(
                    "Updating logs of activation instance "
                    f"{self.latest_instance.id}",
                )
                # TODO: catch exceptions
                self.container_engine.update_logs(
                    self.latest_instance.activation_pod_id,
                    log_handler,
                )
        except engine_exceptions.ContainerEngineError as e:
            # TODO: ensure we handle all the exceptions
            # and we set the status correctly
            self._set_status(ActivationStatus.FAILED, None, "f{e}")
            LOGGER.error(f"Monitor operation Failed {e}")

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
            parent_id=self.db_instance.id,
            id=self.latest_instance.id,
        )

    def _build_credential(self) -> Credential:
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
