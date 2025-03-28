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
from unittest.mock import patch

import pytest

from aap_eda.core.models.rulebook_process import RulebookProcessLog
from aap_eda.services.activation.tee_system_logger import (
    TeeSystemLogger,
    LOGGER,
)

log_test_data = [
    (
        [
            "2023-11-11 01:01:01,908 Hello from ansible-rulebook",
            "DEBUG Received an Event",
            "WARN Event has a warning",
            "CRITICAL Event is critical",
            "FATAL Event is fatal",
            "ERROR MAY DAY MAY DAY, ansible-rulebook going down",
        ],
        [
            ("INFO", "Hello from ansible-rulebook"),
            ("DEBUG", "Received an Event"),
            ("WARNING", "Event has a warning"),
            ("CRITICAL", "Event is critical"),
            ("CRITICAL", "Event is fatal"),
            ("ERROR", "MAY DAY MAY DAY, ansible-rulebook going down"),
        ],
    ),
]


@pytest.mark.parametrize(
    "log_lines, expectations",
    log_test_data,
)
@pytest.mark.django_db
def test_logging(
    caplog_factory, default_activation_instance, log_lines, expectations
):
    """Test that TeeSystemLogger writes to DB and log."""
    logger = logging.getLogger("aap_eda.services.activation.tee_system_logger")
    eda_log = caplog_factory(logger, level=logging.DEBUG)

    obj = TeeSystemLogger(default_activation_instance.id)
    for line in log_lines:
        obj.write(line)
    obj.flush()
    i = 0

    assert len(eda_log.records) == len(expectations)
    for record in eda_log.records:
        assert expectations[i][1] in record.message
        assert record.levelname == expectations[i][0]
        i += 1
    assert RulebookProcessLog.objects.filter(
        activation_instance=default_activation_instance
    ).count() == len(expectations)


@pytest.mark.django_db
def test_logging_exception(caplog_factory, default_activation_instance):
    """Test that TeeSystemLogger writes to DB even if there is exception."""
    eda_log = caplog_factory(LOGGER, level=logging.DEBUG)

    obj = TeeSystemLogger(default_activation_instance.id)
    with patch(
        (
            "aap_eda.services.activation.tee_system_logger."
            "TeeSystemLogger._convert_to_asctime"
        ),
        side_effect=OverflowError,
    ):
        obj.write("Hello with exceptions")
        obj.flush()
        assert (
            RulebookProcessLog.objects.filter(
                activation_instance=default_activation_instance
            ).count()
            == 1
        )
    assert len(eda_log.records) == 1
