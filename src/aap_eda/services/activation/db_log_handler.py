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
from datetime import datetime
from typing import Optional, Union

from django.conf import settings
from django.db import IntegrityError

from aap_eda.core import models
from aap_eda.services.activation.engine.common import LogHandler
from aap_eda.services.activation.engine.exceptions import (
    ContainerUpdateLogsError,
)

LOGGER = logging.getLogger(__name__)


class DBLogger(LogHandler):
    def __init__(self, activation_instance_id: int):
        self.activation_instance_id = activation_instance_id
        self.line_count = 0
        self.activation_instance_log_buffer = []
        if str(settings.ANSIBLE_RULEBOOK_FLUSH_AFTER) == "end":
            self.incremental_flush = False
        else:
            self.flush_after = int(settings.ANSIBLE_RULEBOOK_FLUSH_AFTER)
            self.incremental_flush = True

    def write(
        self,
        lines: Union[list[str], str],
        flush: bool = False,
        timestamp: bool = True,
        log_timestamp: int = 0,
    ) -> None:
        if self.incremental_flush and (
            (self.line_count % self.flush_after) == 0
        ):
            self.flush()

        if not isinstance(lines, list):
            lines = [lines]

        for line in lines:
            if timestamp:
                dt = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]}"
                line = f"{dt} {line}"

            self.activation_instance_log_buffer.append(
                models.RulebookProcessLog(
                    log=line,
                    activation_instance_id=self.activation_instance_id,
                    log_timestamp=log_timestamp,
                )
            )
            self.line_count += 1

        if flush:
            self.flush()

    def flush(self) -> None:
        try:
            if self.activation_instance_log_buffer:
                models.RulebookProcessLog.objects.bulk_create(
                    self.activation_instance_log_buffer
                )
        except IntegrityError:
            message = (
                f"Instance id: {self.activation_instance_id} is not present."
            )
            raise ContainerUpdateLogsError(message)

        self.activation_instance_log_buffer = []

    def get_log_read_at(self) -> Optional[datetime]:
        try:
            activation_instance = models.RulebookProcess.objects.get(
                pk=self.activation_instance_id
            )

            return activation_instance.log_read_at
        except IntegrityError as e:
            raise ContainerUpdateLogsError(str(e))

    def set_log_read_at(self, dt: datetime) -> None:
        try:
            activation_instance = models.RulebookProcess.objects.get(
                pk=self.activation_instance_id
            )
            activation_instance.log_read_at = dt
            activation_instance.save(update_fields=["log_read_at"])
        except IntegrityError as e:
            raise ContainerUpdateLogsError(str(e))

    def num_of_log_lines(self) -> int:
        return models.RulebookProcessLog.objects.filter(
            activation_instance_id=self.activation_instance_id,
        ).count()

    def num_log_write_from(self, log_timestamp: int) -> int:
        return models.RulebookProcessLog.objects.filter(
            activation_instance_id=self.activation_instance_id,
            log_timestamp=log_timestamp,
        ).count()

    def clear_log_write_from(self, log_timestamp: int) -> int:
        try:
            models.RulebookProcessLog.objects.filter(
                activation_instance_id=self.activation_instance_id,
                log_timestamp=log_timestamp,
            ).delete()
        except IntegrityError as e:
            raise ContainerUpdateLogsError(str(e))
