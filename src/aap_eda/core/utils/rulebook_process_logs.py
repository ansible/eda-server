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

import re
from datetime import datetime
from typing import Optional, Tuple

from django.utils.timezone import make_aware

TIMESTAMP_PATTERNS = re.compile(
    r"^(\*{2} )?"
    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r"[ ,.](\d{1,6})"
    r"(?: -)?\s+"  # for '-' or ' '
)

DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S,%f",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S %f",
)


def extract_datetime_and_message_from_log_entry(
    log_entry: str,
) -> Tuple[Optional[datetime], str]:
    """Extract timestamp and message from a log entry.

    Supported formats:
    - "2023-01-01 12:34:56,789 message"
    - "2023-01-01 12:34:56.789 message"
    - "2023-01-01 12:34:56 789 message"
    - "** 2023-01-01 12:34:56.789 - message"

    Args:
        log_entry: Raw log entry string

    Returns:
        Tuple containing parsed datetime (or None) and cleaned message
    """
    match = TIMESTAMP_PATTERNS.match(log_entry)
    if not match:
        return None, log_entry.strip()

    prefix, base_time, microseconds = match.groups()
    timestamp_str = (
        f"{base_time}{'.' if prefix else ','}{microseconds.ljust(6, '0')}"
    )

    for fmt in DATETIME_FORMATS:
        try:
            dt = datetime.strptime(timestamp_str, fmt)
            aware_dt = make_aware(dt)
            break
        except ValueError:
            continue

    message = log_entry[match.end() :].strip()
    if message.startswith("- "):
        message = message[2:]

    return aware_dt, message
