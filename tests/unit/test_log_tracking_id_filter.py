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

import pytest

from aap_eda.utils.log_tracking_id_filter import (
    LogTrackingIdFilter,
    log_tracking_id_var,
)


@pytest.fixture
def log_filter():
    return LogTrackingIdFilter()


@pytest.fixture
def log_record():
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Test message",
        args=None,
        exc_info=None,
    )
    return record


@pytest.fixture(autouse=True)
def reset_context():
    token = log_tracking_id_var.set("default")
    yield
    log_tracking_id_var.reset(token)


def test_filter_with_default_value(log_filter, log_record):
    result = log_filter.filter(log_record)

    assert result is True
    assert log_record.log_tracking_id == "default"


def test_filter_with_custom_value(log_filter, log_record):
    test_id = "test-123"
    log_tracking_id_var.set(test_id)

    result = log_filter.filter(log_record)

    assert result is True
    assert log_record.log_tracking_id == test_id


def test_multiple_filters(log_filter, log_record):
    ids = ["first-111", "second-222"]
    results = []

    for test_id in ids:
        log_tracking_id_var.set(test_id)
        log_filter.filter(log_record)
        results.append(log_record.log_tracking_id)

    assert results == ids
