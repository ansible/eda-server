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
from django.utils import timezone

from aap_eda.api.serializers.activation import is_activation_valid
from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.services.activation import exceptions
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

    @run_with_lock
    def _set_activation_status(
        self,
        status: ActivationStatus,
        status_message: tp.Optional[str] = None,
    ):
        """Set the status from the manager with locking."""
        if status_message:
            self.db_instance.update_status(status, status_message)
        else:
            self.db_instance.update_status(status)

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
            self.db_instance.update_status(
                status=ActivationStatus.ERROR,
                status_message=msg,
            )
            raise exceptions.ActivationStartError(msg)

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
            activation_instance: models.ActivationInstance = (
                self.db_instance.latest_instance
            )
            activation_instance.update_status(ActivationStatus.STARTING)
            log_handler = DBLogger(self.activation_instance.id)

            LOGGER.info(
                "Starting container for activation instance: "
                f"{activation_instance.id}",
            )
            container_request = self._build_container_request()
            container_id = self.container_engine.start(
                container_request,
                log_handler,
            )

            # update status
            self._set_activation_status(ActivationStatus.RUNNING)
            activation_instance.update_status(ActivationStatus.RUNNING)
            activation_instance.activation_pod_id = container_id
            activation_instance.save(update_fields=["activation_pod_id"])

            # update logs
            LOGGER.info(
                "Container start successful. "
                "updating logs for activation instance: "
                f"{activation_instance.id}",
            )
            self.container_engine.update_logs(container_id, log_handler)

        # note(alex): we may need to catch explicit exceptions
        # ActivationImagePullError might need to be handled differently
        # because it can be an error network and we might want to retry
        # so, activation should be in FAILED state to be handled by the monitor
        except exceptions.ActivationException as exc:
            msg = (
                f"Activation {self.db_instance.id} failed to start. "
                f"Reason: {exc}"
            )
            LOGGER.error(msg)
            self._set_activation_status(ActivationStatus.ERROR, msg)
            raise exceptions.ActivationStartError(msg) from exc

    def _is_already_running(self) -> bool:
        if self.db_instance.status == ActivationStatus.RUNNING:
            container_status = None
            latest_instance: tp.Optional[
                models.ActivationInstance
            ] = self.db_instance.latest_instance

            if not latest_instance:
                # how we want to handle this case?
                # for now we raise an error and let the monitor correct it
                msg = f"Activation {self.db_instance.id} has not instances."
                raise exceptions.ActivationStartError(msg)

            if not latest_instance.activation_pod_id:
                # how we want to handle this case?
                # for now we raise an error and let the monitor correct it
                msg = f"Activation {self.db_instance.id} has not pod id."
                raise exceptions.ActivationStartError(msg)

            with contextlib.suppress(exceptions.ActivationPodNotFound):
                container_status = self.container_engine.get_status(
                    container_id=latest_instance.activation_pod_id,
                )

            if latest_instance.status == ActivationStatus.RUNNING and (
                container_status is not None
                and container_status == ActivationStatus.RUNNING
            ):
                return True

            if latest_instance.status == ActivationStatus.RUNNING and (
                container_status is not None
                and container_status != ActivationStatus.RUNNING
            ):
                return False

            if latest_instance.status != ActivationStatus.RUNNING:
                return False

        return False

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

        if self._is_already_running():
            msg = f"Activation {self.db_instance.id} is already running."
            LOGGER.info(msg)
            return
        self._start_activation_instance()

    def restart(self):
        self.stop()
        self.start()

    def monitor(self):
        try:
            self._set_activation_instance()
            status = self.container_engine.get_status(
                self.activation_instance.activation_pod_id
            )
            LOGGER.info(f"Current status is {status}")
            if status in [ActivationStatus.COMPLETED, ActivationStatus.FAILED]:
                self.update_logs()
                log_handler = DBLogger(self.activation_instance.id)
                self.container_engine.cleanup(
                    self.activation_instance.activation_pod_id, log_handler
                )
                self._set_status(status, None)
            elif status == ActivationStatus.RUNNING:
                LOGGER.info("Updating logs")
                self.update_logs()
        except ActivationException as e:
            self._set_status(ActivationStatus.FAILED, None, "f{e}")
            LOGGER.error(f"Monitor Failed {e}")

    def stop(self):
        # TODO: Get the Activation Instance from Activation
        self._set_activation_instance()
        log_handler = DBLogger(self.activation_instance.id)
        self.container_engine.stop(
            self.activation_instance.activation_pod_id, log_handler
        )

    def update_logs(self):
        # TODO: Get the Activation Instance from Activation
        self._set_activation_instance()
        log_handler = DBLogger(self.activation_instance.id)
        self.container_engine.update_logs(
            self.activation_instance.activation_pod_id, log_handler
        )

    def _create_activation_instance(self):
        try:
            self.activation_instance = (
                models.ActivationInstance.objects.create(
                    activation=self.db_instance,
                    name=self.db_instance.name,
                    status=ActivationStatus.STARTING,
                    git_hash=self.db_instance.git_hash,
                )
            )
        except IntegrityError:
            raise exceptions.ActivationRecordNotFound(
                f"Activation {self.db_instance.name} has been deleted."
            )

    def _build_container_request(self) -> ContainerRequest:
        return ContainerRequest(
            credential=self._build_credential(),
            cmdline=self._build_cmdline(),
            name=f"eda-{self.activation_instance.id}-{uuid.uuid4()}",
            image_url=self.db_instance.decision_environment.image_url,
            ports=find_ports(self.db_instance.rulebook_rulesets),
            parent_id=self.db_instance.id,
            id=self.activation_instance.id,
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
            id=str(self.activation_instance.id),
        )

    # TODO: we should access the activation instance from the db_instance.latest_instance
    # activation.status and activation_instance.status not always are the same,
    # I think it is better if we manage them separately
    def _set_activation_instance_status(
        self, status: ActivationStatus, container_id: str, msg: str = None
    ):
        now = timezone.now()
        self.activation_instance.status = status
        self.activation_instance.updated_at = now
        self.activation_instance.activation_pod_id = container_id
        update_fields = ["status", "updated_at", "activation_pod_id"]

        if msg:
            self.activation_instance.status_message = msg
            update_fields.append("status_message")

        self.activation_instance.save(update_fields=update_fields)

        self.db_instance.status = status
        self.db_instance.is_valid = True
        self.db_instance.status_updated_at = now
        update_fields = [
            "status",
            "status_updated_at",
            "is_valid",
            "modified_at",
        ]
        if msg:
            self.db_instance.status_message = msg
            update_fields.append("status_message")

        self.db_instance.save(update_fields=update_fields)

    def _set_activation_instance(self):
        self.activation_instance = models.ActivationInstance.objects.get(
            pk=self.db_instance.latest_instance
        )
