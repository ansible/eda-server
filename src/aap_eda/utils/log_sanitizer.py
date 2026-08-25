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
import traceback

REDACTED_STRING = "********"

SENSITIVE_FIELD_NAMES = (
    "access_token",
    "api_key",
    "authorization",
    "client_secret",
    "credential",
    "password",
    "private_key",
    "public_key",
    "refresh_token",
    "secret",
    "signature",
    "token",
)

_SENSITIVE_FIELDS_RE = "|".join(re.escape(f) for f in SENSITIVE_FIELD_NAMES)

# PEM markers per RFC 7468: exactly 5 dashes, uppercase label.
_PEM_BLOCK_PATTERN = re.compile(
    rf"\"?({_SENSITIVE_FIELDS_RE})\"?(\s*[:=]\s*)\"?"
    r"(-----BEGIN\s[A-Z\s]+-----.*?-----END\s[A-Z\s]+-----)",
    re.IGNORECASE | re.DOTALL,
)

_SENSITIVE_KV_PATTERN = re.compile(
    rf"\"?({_SENSITIVE_FIELDS_RE})\"?(\s*[:=]\s*)\"?(?:.+)",
    re.IGNORECASE,
)


def sanitize_string(text: str) -> str:
    """Redact sensitive key=value pairs and Authorization headers.

    Applies regex substitution to mask values following sensitive
    field names (e.g. ``token=abc123``) and Authorization header
    values (e.g. ``Authorization: Bearer abc123``).

    Args:
        text: The input string to sanitize. Non-string values are
            returned unchanged.

    Returns:
        The input string with sensitive values replaced by the
        REDACTED constant.
    """
    if not isinstance(text, str):
        return text

    text = _PEM_BLOCK_PATTERN.sub(rf"\1\2{REDACTED_STRING}", text)
    text = _SENSITIVE_KV_PATTERN.sub(rf"\1\2{REDACTED_STRING}", text)
    return text


class SensitiveDataFilter(logging.Filter):
    """Logging filter that redacts sensitive data from log records.

    Formats the log message first via ``record.getMessage()``, then
    applies ``sanitize_string`` to the fully interpolated text.
    Exception tracebacks attached via ``exc_info`` are also
    pre-formatted and sanitized before handlers can emit them.
    This avoids corrupting %-format placeholders while ensuring
    all sensitive values are redacted. Attach this filter to logging
    handlers via the Django LOGGING configuration to provide
    defense-in-depth against accidental credential leakage.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Sanitize the log record message and exception traceback.

        Args:
            record: The log record to inspect and sanitize.

        Returns:
            Always ``True`` so the record is emitted after sanitization.
        """
        record.msg = sanitize_string(record.getMessage())
        record.args = None

        if record.exc_info:
            record.exc_text = sanitize_string(
                "".join(traceback.format_exception(*record.exc_info))
            )
            record.exc_info = None

        return True
