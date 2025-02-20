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
import sys


class UnconditionalLogger:
    """Log unconditional messages regardless of log level."""

    unconditional_level = sys.maxsize
    unconditional_level_name = "ALWAYS"

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        logging.addLevelName(
            self.unconditional_level,
            self.unconditional_level_name,
        )

    def log(self, *args, **kwargs):
        """Log at the unconditional level."""
        self.logger.log(self.unconditional_level, *args, **kwargs)
