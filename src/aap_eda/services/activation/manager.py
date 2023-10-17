import logging
import typing as tp
import uuid
from functools import wraps

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils import timezone

import aap_eda.core.models as models
from aap_eda.core.enums import ActivationStatus
from aap_eda.services.activation.engine.common import (
    AnsibleRulebookCmdLine,
    ContainerRequest,
    Credential,
)

from .db_log_handler import DBLogger
from .engine.common import ContainerEngine
from .engine.factory import new_container_engine
from .engine.ports import find_ports
from .exceptions import ActivationException, ActivationRecordNotFound

LOGGER = logging.getLogger(__name__)
ACTIVATION_PATH = "/api/eda/ws/ansible-rulebook"


class ActivationStartError(Exception):
    pass


class HasDbInstance(tp.Protocol):
    db_instance: tp.Any


def run_with_lock(func: tp.Callable) -> tp.Callable:
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
    def __init__(
        self,
        db_instance: models.Activation,
        container_engine: ContainerEngine = None,
    ):
        self.db_instance = db_instance
        if container_engine:
            self.container_engine = container_engine
        else:
            self.container_engine = new_container_engine(db_instance.id)

    @run_with_lock
    def _check_start_requirements(self):
        disallowed_statuses = [
            ActivationStatus.STARTING,
            ActivationStatus.DELETING,
        ]
        self.db_instance.refresh_from_db
        if self.db_instance.status in disallowed_statuses:
            msg = f"Activation {self.db_instance.id} is in "
            "f{self.db_instance.status} state, can not be started"
            LOGGER.warning(msg)
            raise ActivationStartError(msg)
        if self.db_instance.is_enabled is False:
            msg = f"Activation {self.db_instance.id} is disabled. "
            "Can not be started"
            LOGGER.warning(msg)
            raise ActivationStartError(msg)

        # call is_valid_activation from
        # https://github.com/ansible/eda-server/pull/424
        # TODO: Enable once the PR is merged
        is_valid = True
        error = None
        # TODO: is_valid, error = is_activation_valid(self.db_instance)
        if is_valid is False:
            msg = f"Activation {self.db_instance.id} is not valid. "
            f"Error: {error}"
            LOGGER.error(msg)
            self.db_instance.update_status(
                status=ActivationStatus.ERROR, status_message=msg
            )
            raise ActivationStartError(msg)

        if self.db_instance.status == ActivationStatus.RUNNING:
            # check if the container is running
            pass

    def start(self):
        """Start an activation.

        Ensure that the activation meets all the requirements to start,
        otherwise raise ActivationStartError.
        Starts the activation in an idepotent way.
        """
        # Check for the right statuses
        # It may need to be encapsulated in a private method
        try:
            self._check_start_requirements()
        except ObjectDoesNotExist:
            raise ActivationStartError(
                "The Activation instance does not exist."
            )
        try:
            # create an activation instance
            self._create_activation_instance()
            # TODO: The log handler needs the activation instance id
            log_handler = DBLogger(self.activation_instance.id)

            # build a container request
            request = self._build_container_request()
            # start a container
            container_id = self.container_engine.start(request, log_handler)
            # update status
            self._set_status(ActivationStatus.RUNNING, container_id)

            # update logs
            self.container_engine.update_logs(container_id, log_handler)
        except ActivationException as e:
            self._set_status(ActivationStatus.ERROR, None, f"{e}")

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
            self.db_instance.latest_instance = self.activation_instance.id
            self.db_instance.save(
                update_fields=[
                    "latest_instance",
                ]
            )
        except IntegrityError:
            raise ActivationRecordNotFound(
                f"Activation {self.db_instance.name} has been deleted."
            )

    def _build_container_request(self) -> ContainerRequest:
        return ContainerRequest(
            credential=self._build_credential(),
            cmdline=self._build_cmdline(),
            name=f"eda-{self.activation_instance.id}-{uuid.uuid4()}",
            image_url=self.db_instance.decision_environment.image_url,
            ports=self._find_ports(),
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

    def _set_status(
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

    def _find_ports(self):
        found_ports = find_ports(self.db_instance.rulebook_rulesets)

        return self.container_engine.get_ports(found_ports)
