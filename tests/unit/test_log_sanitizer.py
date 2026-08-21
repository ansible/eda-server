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
import sys

import pytest

from aap_eda.utils.log_sanitizer import (
    REDACTED_STRING,
    SensitiveDataFilter,
    sanitize_string,
)


class TestSanitizeString:
    def test_redacts_key_value_with_equals(self):
        text = "config loaded with token=abc123"
        result = sanitize_string(text)
        assert "abc123" not in result
        assert f"token={REDACTED_STRING}" in result

    def test_redacts_key_value_with_colon(self):
        text = "password: my-secret-password"
        result = sanitize_string(text)
        assert "my-secret-password" not in result
        assert f"password: {REDACTED_STRING}" in result

    def test_redacts_authorization_bearer_header(self):
        result = sanitize_string("Authorization: Bearer eyJhbG.pay.sig")
        assert "eyJhbG" not in result
        assert "pay" not in result
        assert REDACTED_STRING in result

    def test_redacts_authorization_key_value(self):
        result = sanitize_string("authorization=tok123")
        assert "tok123" not in result
        assert REDACTED_STRING in result

    def test_redacts_authorization_case_mismatch(self):
        result = sanitize_string("AUTHORIZATION: BEARER MYTOKEN")
        assert "MYTOKEN" not in result
        assert REDACTED_STRING in result

    def test_redacts_access_token_with_bearer_prefix(self):
        result = sanitize_string("access_token=Bearer eyJhbG")
        assert "eyJhbG" not in result
        assert "Bearer" not in result
        assert REDACTED_STRING in result

    def test_redacts_non_standard_auth_scheme(self):
        result = sanitize_string(
            'Authorization: Digest username="admin", realm="test"'
        )
        assert "admin" not in result
        assert "Digest" not in result
        assert REDACTED_STRING in result

    def test_preserves_non_sensitive_text(self):
        text = "Starting container on port 8080 with name eda-worker"
        assert sanitize_string(text) == text

    def test_non_string_passthrough(self):
        assert sanitize_string(42) == 42
        assert sanitize_string(None) is None

    def test_empty_string(self):
        assert sanitize_string("") == ""

    def test_redacts_multi_word_values(self):
        text = "public_key=-----BEGIN PUBLIC KEY----- MIGbMBAG"
        result = sanitize_string(text)
        assert "BEGIN PUBLIC KEY" not in result
        assert "MIGbMBAG" not in result

    def test_redacts_value_starting_with_bearer(self):
        text = "access_token=Bearer eyJhbG"
        result = sanitize_string(text)
        assert "eyJhbG" not in result

    def test_case_insensitive(self):
        text = "SECRET=my_value"
        result = sanitize_string(text)
        assert "my_value" not in result

    def test_redacts_json_quoted_key(self):
        text = '{"token": "abc123"}'
        result = sanitize_string(text)
        assert "abc123" not in result
        assert REDACTED_STRING in result

    def test_redacts_multiline_pem(self):
        text = (
            "private_key=-----BEGIN KEY-----\n"
            "MIILineTwo\n"
            "-----END KEY-----"
        )
        result = sanitize_string(text)
        assert "MIILineTwo" not in result
        assert REDACTED_STRING in result


class TestSensitiveDataFilter:
    @pytest.fixture
    def log_filter(self):
        return SensitiveDataFilter()

    def test_sanitizes_formatted_message(self, log_filter):
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg="Login with password=%s",
            args=("secret123",),
            exc_info=None,
        )
        log_filter.filter(record)

        assert "secret123" not in record.msg
        assert REDACTED_STRING in record.msg
        assert record.args is None

    def test_preserves_format_placeholders(self, log_filter):
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg="password: %s",
            args=("hunter2",),
            exc_info=None,
        )
        log_filter.filter(record)

        assert "hunter2" not in record.msg
        assert record.args is None

    def test_always_returns_true(self, log_filter):
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg="normal message",
            args=None,
            exc_info=None,
        )
        assert log_filter.filter(record) is True

    def test_sanitizes_exception_traceback(self, log_filter):
        try:
            raise ValueError("token=leaked_value")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="An error occurred",
            args=None,
            exc_info=exc_info,
        )
        log_filter.filter(record)

        assert "leaked_value" not in record.exc_text
        assert REDACTED_STRING in record.exc_text
        assert record.exc_info is None

    def test_integration_with_logger(self, caplog):
        logger_name = "test.sensitive_data_filter"
        test_logger = logging.getLogger(logger_name)
        test_logger.addFilter(SensitiveDataFilter())
        try:
            with caplog.at_level(logging.DEBUG, logger=logger_name):
                test_logger.debug("Connecting with password=supersecret")

            assert "supersecret" not in caplog.text
            assert REDACTED_STRING in caplog.text
        finally:
            test_logger.filters.clear()
