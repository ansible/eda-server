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

from importlib.metadata import PackageNotFoundError, version
from unittest.mock import patch

import pytest

from aap_eda.core.utils.strings import extract_variables
from aap_eda.utils import get_eda_version, str_to_bool


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("True", True),
        ("False", False),
        ("false", False),
        ("yes", True),
        ("no", False),
        ("1", True),
        ("0", False),
        ("", False),
        ("anything", False),
    ],
)
def test_str_to_bool(value, expected):
    assert str_to_bool(value) == expected


def test_get_eda_version():
    assert get_eda_version() == version("aap-eda")

    # assert outcome when aap-eda package is not found
    with patch("importlib.metadata.version", side_effect=PackageNotFoundError):
        assert get_eda_version() == "unknown"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("simple", set()),
        (
            "And this is a {{demo}}",
            {
                "demo",
            },
        ),
        (
            "{{var1}} and {{var2}}",
            {
                "var1",
                "var2",
            },
        ),
    ],
)
def test_extract_variables(value, expected):
    assert extract_variables(value) == expected
