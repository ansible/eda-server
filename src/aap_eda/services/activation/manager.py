from .factory import new_container_engine, ContainerEngine
import aap_eda.core.models as models
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from functools import wraps
from aap_eda.core.enums import ActivationStatus
import typing as tp


class ActivationStartError(Exception):
    pass


class HasDbInstance(tp.Protocol):
    db_instance: tp.Any  # or you can be more specific with the type, if desired


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

    def _set_status():
        pass

    def _get_status(self):
        pass

    @run_with_lock
    def _check_start_requirements(self):
        disallowed_statuses = [
            ActivationStatus.STARTING,
            ActivationStatus.DELETING,
        ]

        if self.db_instance.status in disallowed_statuses:
            raise ActivationStartError(
                f"Activation is in {self.db_instance.status} state.",
            )
        if self.db_instance.is_enabled is False:
            raise ActivationStartError("Activation is disabled.")

        # call is_valid_activation from https://github.com/ansible/eda-server/pull/424
        is_valid, error = is_activation_valid(self.db_instance)
        if is_valid is False:
            msg = f"Activation {self.db_instance.id} is not valid. {error}"
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
        # Check for a container
        # start a container
        # update status
        # update logs

    def restart(self):
        pass

    def monitor(self):
        self.restart()

    def update_logs(self):
        pass
