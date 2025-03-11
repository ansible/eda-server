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

from aap_eda.services.activation.db_log_handler import DBLogger


class TeeSystemLogger(DBLogger):
    """
    A logging class that extends DBLogger to log messages both to the database
    and the system logger.
    """

    def __init__(self, activation_instance_id: int, logger: logging.Logger):
        super().__init__(activation_instance_id)
        self.logger = logger

    def write(
        self,
        lines: Union[list[str], str],
        flush: bool = False,
        timestamp: bool = True,
        log_timestamp: int = 0,
    ) -> None:

        if not isinstance(lines, list):
            lines = [lines]

        prefixed_lines = [self.prefix + line for line in lines]

        # Call the parent write method to log to the database
        super().write(prefixed_lines, lines, flush, timestamp, log_timestamp)

        for line in lines:
            # Determine the log level
            if "ERROR" in line:
                log_level = logging.ERROR
            elif "WARN" in line:
                log_level = logging.WARNING
            elif "DEBUG" in line:
                log_level = logging.DEBUG
            elif "CRITICAL" in line or "FATAL" in line:
                log_level = logging.CRITICAL
            else:
                log_level = logging.INFO

            self.logger.log(log_level, line)
