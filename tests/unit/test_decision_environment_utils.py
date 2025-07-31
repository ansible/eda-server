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

import pytest

from aap_eda.core.enums import ImagePullPolicy
from aap_eda.core.utils.decision_environment import (
    convert_pull_policy_from_frontend,
    convert_pull_policy_to_frontend,
)

# Tests for convert_pull_policy_to_frontend function


@pytest.mark.parametrize(
    "internal_policy,expected_frontend",
    [
        (ImagePullPolicy.ALWAYS, "always"),
        (ImagePullPolicy.NEVER, "never"),
        (ImagePullPolicy.IF_NOT_PRESENT, "missing"),
    ],
)
def test_convert_pull_policy_to_frontend_valid_policies(
    internal_policy, expected_frontend
):
    """Test valid internal policy values are converted correctly."""
    result = convert_pull_policy_to_frontend(internal_policy)
    assert result == expected_frontend


@pytest.mark.parametrize(
    "invalid_policy",
    [
        "unknown_policy",
        "invalid",
        "",
        None,
        123,
    ],
)
def test_convert_pull_policy_to_frontend_invalid_policies_return_default(
    invalid_policy,
):
    """Test invalid/unknown policy values return the default 'always'."""
    result = convert_pull_policy_to_frontend(invalid_policy)
    assert result == "always"


# Tests for convert_pull_policy_from_frontend function


def test_convert_pull_policy_from_frontend_empty_or_none_values():
    """Test that empty or None values are returned directly."""
    assert convert_pull_policy_from_frontend("") == ""
    assert convert_pull_policy_from_frontend(None) is None
    assert convert_pull_policy_from_frontend(0) == 0
    assert convert_pull_policy_from_frontend(False) is False


@pytest.mark.parametrize(
    "frontend_policy,expected_internal",
    [
        ("always", ImagePullPolicy.ALWAYS),
        ("never", ImagePullPolicy.NEVER),
        ("missing", ImagePullPolicy.IF_NOT_PRESENT),
    ],
)
def test_convert_pull_policy_from_frontend_valid_policies(
    frontend_policy, expected_internal
):
    """Test valid frontend policy strings are converted correctly."""
    result = convert_pull_policy_from_frontend(frontend_policy)
    assert result == expected_internal


@pytest.mark.parametrize(
    "internal_policy",
    [
        ImagePullPolicy.ALWAYS,
        ImagePullPolicy.NEVER,
        ImagePullPolicy.IF_NOT_PRESENT,
    ],
)
def test_convert_pull_policy_from_frontend_backward_compatibility(
    internal_policy,
):
    """Test internal enum values should return the same value."""
    result = convert_pull_policy_from_frontend(internal_policy)
    assert result == internal_policy


@pytest.mark.parametrize(
    "unknown_policy",
    [
        "unknown",
        "invalid_policy",
        "ALWAYS",  # Uppercase version
        "NEVER",  # Uppercase version
        "Missing",  # Title case
        123,
        "if_not_present",  # Underscore version
    ],
)
def test_convert_pull_policy_from_frontend_unknown_policies_return_original(
    unknown_policy,
):
    """Test that unknown policy values return the original value."""
    result = convert_pull_policy_from_frontend(unknown_policy)
    assert result == unknown_policy


def test_convert_pull_policy_from_frontend_case_sensitivity():
    """Test case sensitivity of frontend mapping."""
    # Only exact lowercase matches should be converted
    assert (
        convert_pull_policy_from_frontend("always") == ImagePullPolicy.ALWAYS
    )
    assert (
        convert_pull_policy_from_frontend("Always") == "Always"
    )  # Returns original
    assert (
        convert_pull_policy_from_frontend("ALWAYS") == "ALWAYS"
    )  # Returns original


def test_convert_pull_policy_from_frontend_comprehensive_mapping_coverage():
    """Test comprehensive coverage of mapping dictionary."""
    # Test all mapping entries are handled correctly
    frontend_to_internal = {
        "always": ImagePullPolicy.ALWAYS,
        "never": ImagePullPolicy.NEVER,
        "missing": ImagePullPolicy.IF_NOT_PRESENT,
    }

    internal_to_internal = {
        ImagePullPolicy.ALWAYS: ImagePullPolicy.ALWAYS,
        ImagePullPolicy.NEVER: ImagePullPolicy.NEVER,
        ImagePullPolicy.IF_NOT_PRESENT: ImagePullPolicy.IF_NOT_PRESENT,
    }

    # Test frontend to internal mapping
    for frontend, expected_internal in frontend_to_internal.items():
        result = convert_pull_policy_from_frontend(frontend)
        assert result == expected_internal

    # Test internal to internal mapping (backward compatibility)
    for internal, expected_internal in internal_to_internal.items():
        result = convert_pull_policy_from_frontend(internal)
        assert result == expected_internal


# Integration tests for both functions


def test_round_trip_conversion():
    """Test consistency of round-trip conversion."""
    # Internal -> Frontend -> Internal should remain consistent
    for internal_policy in [
        ImagePullPolicy.ALWAYS,
        ImagePullPolicy.NEVER,
        ImagePullPolicy.IF_NOT_PRESENT,
    ]:
        frontend = convert_pull_policy_to_frontend(internal_policy)
        back_to_internal = convert_pull_policy_from_frontend(frontend)
        assert back_to_internal == internal_policy


def test_default_behavior_consistency():
    """Test consistency of default behavior."""
    # to_frontend default is "always"
    unknown_to_frontend = convert_pull_policy_to_frontend("unknown")
    assert unknown_to_frontend == "always"

    # from_frontend returns original value for unknown input
    unknown_from_frontend = convert_pull_policy_from_frontend("unknown")
    assert unknown_from_frontend == "unknown"


def test_enum_values_consistency():
    """Test consistency of enum values."""
    # Ensure the enum values we're testing match the actual definitions
    assert ImagePullPolicy.ALWAYS == "Always"
    assert ImagePullPolicy.NEVER == "Never"
    assert ImagePullPolicy.IF_NOT_PRESENT == "IfNotPresent"
