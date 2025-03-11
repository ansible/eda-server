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

from aap_eda.settings.post_load import configure_logging

LOGGER = logging.getLogger(__name__)


def test_configure_logging():
    """Test that configure_logging sets the correct log level and format."""
    configure_logging()

    # Verify logging level is set to DEBUG
    assert LOGGER.level == logging.DEBUG, "Logging level should be DEBUG"

    # Ensure the format includes 'rulebook_timestamp'
    formatter = LOGGER.handlers[0].formatter
    assert (
        formatter._fmt
        == "%(rulebook_timestamp)s - %(levelname)s - %(message)s"
    ), "Log format is incorrect"


def test_logging_output(caplog):
    """Test that a log message follows the expected format."""
    configure_logging()

    with caplog.at_level(logging.DEBUG):
        LOGGER.debug("This is a debug log")

    # Verify the logged message is captured
    assert "This is a debug log" in caplog.text
    assert "DEBUG" in caplog.text
