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
from rest_framework import status

from aap_eda.api.exceptions import (
    WorkerUnavailable,
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

    with mock.patch(
        "rest_framework.views.exception_handler"
    ) as mock_handler, mock.patch.dict(settings.__dict__, {"DEBUG": False}):
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


def test_worker_unavailable_exception():
    """Test WorkerUnavailable exception with default values."""
    exc = WorkerUnavailable()

    assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc.default_code == "worker_unavailable"
    assert str(exc.default_detail) == (
        "Workers are currently unavailable. Please try again later."
    )
    assert str(exc) == (
        "Workers are currently unavailable. Please try again later."
    )


def test_worker_unavailable_exception_with_custom_detail():
    """Test WorkerUnavailable exception with custom detail message."""
    custom_detail = "Custom worker unavailable message"
    exc = WorkerUnavailable(detail=custom_detail)

    assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc.default_code == "worker_unavailable"
    assert str(exc) == custom_detail


def test_worker_unavailable_exception_with_custom_code():
    """Test WorkerUnavailable exception with custom error code."""
    custom_code = "custom_worker_error"
    exc = WorkerUnavailable(code=custom_code)

    assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert (
        exc.default_code == "worker_unavailable"
    )  # default_code doesn't change
    assert str(exc) == (
        "Workers are currently unavailable. Please try again later."
    )


def test_worker_unavailable_exception_with_custom_detail_and_code():
    """Test WorkerUnavailable exception with both custom detail and code."""
    custom_detail = "Specific worker service is down"
    custom_code = "specific_worker_error"
    exc = WorkerUnavailable(detail=custom_detail, code=custom_code)

    assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc.default_code == "worker_unavailable"
    assert str(exc) == custom_detail


def test_worker_unavailable_exception_attributes():
    """Test that WorkerUnavailable exception has correct class attributes."""
    # Test class attributes directly
    assert WorkerUnavailable.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert WorkerUnavailable.default_code == "worker_unavailable"
    assert WorkerUnavailable.default_detail == (
        "Workers are currently unavailable. Please try again later."
    )


def test_worker_unavailable_exception_raising():
    """Test raising and catching WorkerUnavailable exception."""
    with pytest.raises(WorkerUnavailable) as exc_info:
        raise WorkerUnavailable()

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert str(exc_info.value) == (
        "Workers are currently unavailable. Please try again later."
    )


def test_worker_unavailable_exception_raising_with_custom_message():
    """Test raising WorkerUnavailable exception with custom message."""
    custom_message = "Project workers are temporarily down"

    with pytest.raises(WorkerUnavailable) as exc_info:
        raise WorkerUnavailable(detail=custom_message)

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert str(exc_info.value) == custom_message


def test_worker_unavailable_exception_with_worker_type_project():
    """Test WorkerUnavailable exception with project worker type."""
    exc = WorkerUnavailable(worker_type="project")

    assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc.default_code == "worker_unavailable"
    assert str(exc) == (
        "Project workers are currently unavailable. Please try again later."
    )


def test_worker_unavailable_exception_with_worker_type_activation():
    """Test WorkerUnavailable exception with activation worker type."""
    exc = WorkerUnavailable(worker_type="activation")

    assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc.default_code == "worker_unavailable"
    assert str(exc) == (
        "Activation workers are currently unavailable. Please try again later."
    )


def test_worker_unavailable_exception_worker_type_with_custom_detail():
    """Test that custom detail overrides worker_type message."""
    custom_detail = "Custom worker message"
    exc = WorkerUnavailable(detail=custom_detail, worker_type="project")

    assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert str(exc) == custom_detail  # Custom detail should take precedence


def test_worker_unavailable_exception_worker_type_capitalization():
    """Test that worker_type is properly capitalized in messages."""
    exc_lower = WorkerUnavailable(worker_type="project")
    exc_mixed = WorkerUnavailable(worker_type="PrOjEcT")

    assert "Project workers" in str(exc_lower)
    assert "Project workers" in str(exc_mixed)
