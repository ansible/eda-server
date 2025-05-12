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
import importlib.metadata
import logging
import re
from functools import cache

logger = logging.getLogger(__name__)


def str_to_bool(value: str) -> bool:
    return value.lower() in ("yes", "true", "1")


def get_package_version(package_name: str) -> str:
    """Return version of the given package."""
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        logger.error(
            "The package '%s' is not installed; returning 'unknown' "
            "version for it",
            package_name,
        )
        return "unknown"


@cache
def sanitize_postgres_identifier(identifier: str) -> str:
    """
    Sanitize an input string to conform to PostgreSQL identifier rules.

    Initially intended to be used for pg_notify channel names.
    """
    max_identifier_length = 63
    if not identifier:
        raise ValueError("Identifier cannot be empty.")

    # Replace invalid characters with underscores
    sanitized = re.sub(r"\W", "_", identifier)

    # Ensure it starts with a valid character
    if not re.match(r"[A-Za-z_]", sanitized[0]):
        sanitized = f"_{sanitized}"

    # Ensure length
    if len(sanitized) > max_identifier_length:
        raise ValueError(
            f"Sanitized channel name exceeds {max_identifier_length} "
            "characters."
        )

    return sanitized
