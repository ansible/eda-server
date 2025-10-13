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
from unittest import mock

import pytest
from django.conf import settings

from aap_eda.api.exceptions import (
    api_fallback_handler,
    log_exception_without_data,
    logger,
)


@pytest.fixture
def eda_caplog(caplog_factory):
    return caplog_factory(logger)


def test_trigger_fallback_handler():
    exc = ValueError("Test error")
    context = {"view": mock.MagicMock()}

    with (
        mock.patch("rest_framework.views.exception_handler") as mock_handler,
        mock.patch.dict(settings.__dict__, {"DEBUG": False}),
    ):
        mock_handler.return_value = None
        log_mock = mock.Mock()

        with mock.patch(
            "aap_eda.api.exceptions.log_exception_without_data", log_mock
        ):
            response = api_fallback_handler(exc, context)

    assert response.status_code == 500
    log_mock.assert_called_once_with(ValueError, exc, exc.__traceback__)


def test_log_exception_with_traceback(eda_caplog):
    eda_caplog.set_level(logging.ERROR)
    try:
        raise ValueError("Test error")
    except ValueError as e:
        exc_type, exc_value, exc_traceback = type(e), e, e.__traceback__

    log_exception_without_data(exc_type, exc_value, exc_traceback)

    assert len(eda_caplog.records) >= 1
    first_record = eda_caplog.records[0]
    assert first_record.message == "ValueError: Test error"

    for record in eda_caplog.records[1:]:
        parts = record.message.split(":")
        assert len(parts) >= 2
        assert parts[0].endswith(".py")
