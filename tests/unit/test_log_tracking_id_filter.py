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
from unittest import mock

import pytest

from aap_eda.utils.log_tracking_id_filter import LogTrackingIdFilter


@pytest.fixture
def log_filter():
    return LogTrackingIdFilter()


@pytest.fixture
def mock_record():
    return mock.Mock()


def test_filter_with_values(log_filter, mock_record):
    with mock.patch(
        "aap_eda.utils.log_tracking_id_filter.get_log_tracking_id"
    ) as mock_tracking, mock.patch(
        "aap_eda.utils.log_tracking_id_filter.get_request_id"
    ) as mock_request:
        mock_tracking.return_value = "test_tracking_id"
        mock_request.return_value = "test_request_id"

        result = log_filter.filter(mock_record)

        assert mock_record.log_tracking_id == "test_tracking_id"
        assert mock_record.request_id == "test_request_id"
        assert result is True
