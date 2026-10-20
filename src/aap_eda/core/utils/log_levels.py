#  Copyright 2026 Red Hat, Inc.
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
import re
from typing import Optional

_LOG_LEVEL_HEADER = re.compile(
    r"^(?:\[[^\]\r\n]+\]\s+)?"
    r"(?P<level>DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL)(?:\s|$)",
    re.IGNORECASE,
)
_BRACKETED_DEBUG_HEADER = re.compile(r"^\[debug\](?:\s|$)", re.IGNORECASE)

_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
    "FATAL": logging.CRITICAL,
}


def classify_log_level(message: str) -> Optional[int]:
    """Return the Python logging level from a leading severity header.

    ``None`` indicates that the message has no recognized severity header.
    Callers that use the result for filtering should retain such messages.
    """
    if _BRACKETED_DEBUG_HEADER.match(message):
        return logging.DEBUG

    match = _LOG_LEVEL_HEADER.match(message)
    if match is None:
        return None

    return _LOG_LEVELS[match.group("level").upper()]
