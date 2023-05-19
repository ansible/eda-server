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
from typing import Union

from django.conf import settings

from aap_eda.core import models

logger = logging.getLogger(__name__)


class ActivationDbLogger:
    def __init__(self, activation_instance_id: int):
        self.line_number = 0
        self.activation_instance_id = activation_instance_id
        self.activation_instance_log_buffer = []
        if str(settings.ANSIBLE_RULEBOOK_FLUSH_AFTER) == "end":
            self.incremental_flush = False
            logger.info("Log flush setting: end")
        else:
            self.flush_after = int(settings.ANSIBLE_RULEBOOK_FLUSH_AFTER)
            self.incremental_flush = True
            logger.info(f"Log flush setting: {self.flush_after}")

    def lines_written(self) -> int:
        return self.line_number

    def write(self, lines: Union[list[str], str], flush=False) -> None:
        if self.incremental_flush and self.line_number % self.flush_after == 0:
            self.flush()

        if not isinstance(lines, list):
            lines = [lines]

        for line in lines:
            self.activation_instance_log_buffer.append(
                models.ActivationInstanceLog(
                    line_number=self.line_number,
                    log=line,
                    activation_instance_id=self.activation_instance_id,
                )
            )
            self.line_number += 1

        if flush:
            self.flush()

    def flush(self) -> None:
        if self.activation_instance_log_buffer:
            models.ActivationInstanceLog.objects.bulk_create(
                self.activation_instance_log_buffer
            )
        self.activation_instance_log_buffer = []
