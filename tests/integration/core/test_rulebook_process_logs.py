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

from datetime import datetime

import pytest
from django.utils.timezone import make_aware

from aap_eda.core.utils.rulebook_process_logs import (
    extract_datetime_and_message_from_log_entry,
)


@pytest.mark.parametrize(
    ("log_entry", "expected_dt", "expected_msg"),
    [
        (
            "2025-01-17 18:39:49,191 Starting Container",
            make_aware(datetime(2025, 1, 17, 18, 39, 49, 191000)),
            "Starting Container",
        ),
        (
            "2025-01-17 18:39:55,215 - ansible_rulebook.action.run_job_template",  # noqa: E501
            make_aware(datetime(2025, 1, 17, 18, 39, 55, 215000)),
            "ansible_rulebook.action.run_job_template",
        ),
        (
            "** 2025-01-17 18:39:55.222773 [debug] ****",
            make_aware(datetime(2025, 1, 17, 18, 39, 55, 222773)),
            "[debug] ****",
        ),
        (
            "2025-01-17 18:43:38 638 [main] DEBUG org.drools.ansible",
            make_aware(datetime(2025, 1, 17, 18, 43, 38, 638000)),
            "[main] DEBUG org.drools.ansible",
        ),
        (
            "2025-01-17 18:39:55,215   - message with ending spaces   ",
            make_aware(datetime(2025, 1, 17, 18, 39, 55, 215000)),
            "message with ending spaces",
        ),
        (
            "** 2025-01-17 18:39:55.222773 - [test] message",
            make_aware(datetime(2025, 1, 17, 18, 39, 55, 222773)),
            "[test] message",
        ),
        (
            "Ruleset: Long Running Range",
            None,
            "Ruleset: Long Running Range",
        ),
    ],
)
def test_extract_datetimes(
    log_entry: str,
    expected_dt: str,
    expected_msg: str,
):
    dt, message = extract_datetime_and_message_from_log_entry(log_entry)

    assert dt == expected_dt
    assert message == expected_msg
