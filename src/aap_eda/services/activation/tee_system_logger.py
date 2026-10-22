#  Copyright 2025 Red Hat, Inc.
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
from datetime import datetime, timezone

from aap_eda.services.activation.db_log_handler import DBLogger

EXCEPTIONS_TO_CATCH = (
    OverflowError,
    OSError,
    ValueError,
    TypeError,
    AttributeError,
    KeyError,
)

LOGGER = logging.getLogger(__name__)

LOG_LEVEL_SEARCH_INDEX = 40


class TeeSystemLogger(DBLogger):
    """
    A logging class that extends DBLogger.

    It adds log messages both to the database and the system logger.
    """

    @staticmethod
    def _convert_to_asctime(timestamp: int) -> str:
        """Convert a UNIX timestamp to asctime format in UTC."""
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S,%f"
        )[:-3]

    def flush(self):
        try:
            for buffer in self.activation_instance_log_buffer:
                line = buffer.log
                rulebook_timestamp = self._convert_to_asctime(
                    buffer.log_timestamp
                )

                substring = line[:LOG_LEVEL_SEARCH_INDEX]
                if "ERROR" in substring:
                    log_level = logging.ERROR
                elif "WARN" in substring:
                    log_level = logging.WARNING
                elif "DEBUG" in substring:
                    log_level = logging.DEBUG
                elif "CRITICAL" in substring or "FATAL" in substring:
                    log_level = logging.CRITICAL
                else:
                    log_level = logging.INFO

                extra = {
                    "rulebook_timestamp": rulebook_timestamp,
                    "activation_instance_id": self.activation_instance_id,
                }
                LOGGER.log(log_level, line, extra=extra)
        except EXCEPTIONS_TO_CATCH as e:
            extra = {
                "rulebook_timestamp": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S,%f"
                ),
                "activation_instance_id": self.activation_instance_id,
            }
            LOGGER.log(
                logging.ERROR,
                f"Exception caught while writing {e}\n",
                extra=extra,
            )
        finally:
            # This will call the DBLoggers flush which will
            # write to the Database and clear the log buffer
            super().flush()
