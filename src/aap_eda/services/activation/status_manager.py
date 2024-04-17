#  Copyright 2024 Red Hat, Inc.
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

import logging
import typing as tp
from functools import wraps

from django.db import transaction

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus, ProcessParentType

LOGGER = logging.getLogger(__name__)


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


class StatusManager:
    """Status Manager manages the status of a process parent.

    The Status Manager is responsible for updating the status
    of the process parent and its latest instance.
    """

    def __init__(
        self,
        db_instance: tp.Union[models.Activation, models.EventStream],
    ):
        """Initialize the Process Parent Status Manager.

        Args:
            db_instance: The database instance of the process parent.
        """
        self.db_instance = db_instance
        if isinstance(db_instance, models.Activation):
            self.db_instance_type = ProcessParentType.ACTIVATION
        else:
            self.db_instance_type = ProcessParentType.EVENT_STREAM

    @property
    def latest_instance(self) -> tp.Optional[models.RulebookProcess]:
        """Return the latest instance of the activation."""
        return self.db_instance.latest_instance

    def set_latest_instance_status(
        self,
        status: ActivationStatus,
        status_message: tp.Optional[str] = None,
    ):
        """Set the status of the process parent instance from the manager."""
        kwargs = {"status": status}
        if status_message:
            kwargs["status_message"] = status_message
        self.latest_instance.update_status(**kwargs)

    @run_with_lock
    def set_status(
        self,
        status: ActivationStatus,
        status_message: tp.Optional[str] = None,
    ) -> None:
        """Set the status from the manager."""
        kwargs = {"status": status}
        if status_message:
            kwargs["status_message"] = status_message
        self.db_instance.update_status(**kwargs)
