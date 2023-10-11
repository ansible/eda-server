from .engine.factory import new_container_engine
from .engine.common import ContainerEngine
import aap_eda.core.models as models
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from functools import wraps
from aap_eda.core.enums import ActivationStatus
import typing as tp
import logging
from aap_eda.services.activation.engine.common import ContainerRequest

LOGGER = logging.getLogger(__name__)


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
        container_engine: ContainerEngine = new_container_engine(),
    ):
        self.db_instance = db_instance
        self.container_engine = container_engine

    @run_with_lock
    def _check_start_requirements(self):
        disallowed_statuses = [
            ActivationStatus.STARTING,
            ActivationStatus.DELETING,
        ]
        self.db_instance.refresh_from_db
        if self.db_instance.status in disallowed_statuses:
            msg = f"Activation {self.db_instance.id} is in"
            " {self.db_instance.status} state, can not be started"
            LOGGER.warning(msg)
            raise ActivationStartError(msg)
        if self.db_instance.is_enabled is False:
            msg = f"Activation {self.db_instance.id} is disabled. Can not be started"
            LOGGER.warning(msg)
            raise ActivationStartError(msg)

        # call is_valid_activation from https://github.com/ansible/eda-server/pull/424
        is_valid, error = is_activation_valid(self.db_instance)
        if is_valid is False:
            msg = f"Activation {self.db_instance.id} is not valid. Error: {error}"
            LOGGER.error(msg)
            self.db_instance.update_status(
                status=ActivationStatus.ERROR, status_message=msg
            )
            raise ActivationStartError(msg)

        if self.db_instance.status == ActivationStatus.RUNNING:
            # check if the container is running
            pass

    def _build_container_request(self):
        name = eda - {activation_instance.id} - {uuid.uuid4()}
        request = ContainerRequest

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
        # create an activation instance
        # build a container request
        # start a container
        # update status
        # update logs

    def restart(self):
        pass

    def monitor(self):
        self.restart()

    def update_logs(self):
        pass
