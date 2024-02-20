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

from unittest.mock import patch

import pytest

from aap_eda.settings.default import (
    ImproperlyConfigured,
    RulebookProcessLogLevel,
    get_rulebook_process_log_level,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("debug", RulebookProcessLogLevel.DEBUG),
        ("info", RulebookProcessLogLevel.INFO),
        ("error", RulebookProcessLogLevel.ERROR),
        ("-v", RulebookProcessLogLevel.INFO),
        ("-vv", RulebookProcessLogLevel.DEBUG),
    ],
)
@patch("aap_eda.settings.default.settings")
def test_rulebook_log_level(mock_settings, value, expected):
    mock_settings.get.return_value = value

    result = get_rulebook_process_log_level()

    assert result == expected


@patch("aap_eda.settings.default.settings")
def test_rulebook_log_level_invalid(mock_settings):
    mock_settings.get.return_value = "invalid"
    with pytest.raises(ImproperlyConfigured):
        get_rulebook_process_log_level()
