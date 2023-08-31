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
from abc import ABC, abstractmethod
from typing import List

import yaml
from django.db.utils import DatabaseError
from django.utils import timezone

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus

from .activation_db_logger import ActivationDbLogger
from .exceptions import ActivationRecordNotFound

ACTIVATION_PATH = "/api/eda/ws/ansible-rulebook"

logger = logging.getLogger(__name__)


class RulesetHandler(ABC):
    @abstractmethod
    def activate(
        self,
        instance: models.ActivationInstance,
        activation_db_logger: ActivationDbLogger,
    ) -> models.ActivationInstance:
        pass

    @abstractmethod
    def deactivate(
        self,
        instance: models.ActivationInstance,
    ) -> models.ActivationInstance:
        pass

    def save_activation_and_instance(
        self,
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
                ActivationStatus.PENDING,
                ActivationStatus.STARTING,
                ActivationStatus.RUNNING,
                ActivationStatus.UNRESPONSIVE,
            ]
            activation_fields = ["status", "modified_at"]
            if instance.status not in running_states:
                instance.activation.current_job_id = None
                activation_fields.append("current_job_id")
            if instance.status == ActivationStatus.COMPLETED:
                instance.activation.failure_count = 0
                activation_fields.append("failure_count")

            instance.save(update_fields=update_fields)
            instance.activation.save(update_fields=activation_fields)
        except DatabaseError:
            message = f"Failed to update instance [id: {instance.id}]"
            logger.error(message)
            raise ActivationRecordNotFound(message)

    def find_ports(self, rulebook_text: str) -> List:
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
