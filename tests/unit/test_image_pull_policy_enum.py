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


class TestImagePullPolicyEnum:
    """Test the ImagePullPolicy enum methods."""

    def test_enum_values(self):
        """Test enum has correct values."""
        assert ImagePullPolicy.ALWAYS == "Always"
        assert ImagePullPolicy.NEVER == "Never"
        assert ImagePullPolicy.IF_NOT_PRESENT == "IfNotPresent"

    def test_to_k8s_method(self):
        """Test to_k8s() method returns correct Kubernetes format."""
        assert ImagePullPolicy.ALWAYS.to_k8s() == "Always"
        assert ImagePullPolicy.NEVER.to_k8s() == "Never"
        assert ImagePullPolicy.IF_NOT_PRESENT.to_k8s() == "IfNotPresent"

    def test_to_display_method(self):
        """Test to_display() method returns user-friendly format."""
        assert ImagePullPolicy.ALWAYS.to_display() == "always"
        assert ImagePullPolicy.NEVER.to_display() == "never"
        assert ImagePullPolicy.IF_NOT_PRESENT.to_display() == "missing"

    def test_to_podman_method(self):
        """Test to_podman() method returns correct Podman format."""
        assert ImagePullPolicy.ALWAYS.to_podman() == "always"
        assert ImagePullPolicy.NEVER.to_podman() == "never"
        assert ImagePullPolicy.IF_NOT_PRESENT.to_podman() == "missing"

    @pytest.mark.parametrize(
        "input_value,expected_enum",
        [
            # Case-insensitive matching
            ("always", ImagePullPolicy.ALWAYS),
            ("ALWAYS", ImagePullPolicy.ALWAYS),
            ("Always", ImagePullPolicy.ALWAYS),
            ("never", ImagePullPolicy.NEVER),
            ("NEVER", ImagePullPolicy.NEVER),
            ("Never", ImagePullPolicy.NEVER),
            # UI-friendly aliases
            ("missing", ImagePullPolicy.IF_NOT_PRESENT),
            ("MISSING", ImagePullPolicy.IF_NOT_PRESENT),
            ("Missing", ImagePullPolicy.IF_NOT_PRESENT),
            # Internal enum values (backward compatibility)
            ("Always", ImagePullPolicy.ALWAYS),
            ("Never", ImagePullPolicy.NEVER),
            ("IfNotPresent", ImagePullPolicy.IF_NOT_PRESENT),
        ],
    )
    def test_from_user_input_valid_values(self, input_value, expected_enum):
        """Test from_user_input() method with valid values."""
        result = ImagePullPolicy.from_user_input(input_value)
        assert result == expected_enum

    def test_from_user_input_empty_values(self):
        """Test from_user_input() with empty values defaults to ALWAYS."""
        assert ImagePullPolicy.from_user_input("") == ImagePullPolicy.ALWAYS
        assert ImagePullPolicy.from_user_input(None) == ImagePullPolicy.ALWAYS
        assert ImagePullPolicy.from_user_input("   ") == ImagePullPolicy.ALWAYS

    def test_from_user_input_unknown_values(self):
        """Test from_user_input() with unknown values defaults to ALWAYS."""
        assert (
            ImagePullPolicy.from_user_input("unknown")
            == ImagePullPolicy.ALWAYS
        )
        assert (
            ImagePullPolicy.from_user_input("invalid")
            == ImagePullPolicy.ALWAYS
        )
        assert ImagePullPolicy.from_user_input("xyz") == ImagePullPolicy.ALWAYS

    def test_from_user_input_strips_whitespace(self):
        """Test from_user_input() method strips whitespace."""
        assert (
            ImagePullPolicy.from_user_input("  always  ")
            == ImagePullPolicy.ALWAYS
        )
        assert (
            ImagePullPolicy.from_user_input("\tnever\n")
            == ImagePullPolicy.NEVER
        )
        assert (
            ImagePullPolicy.from_user_input(" missing ")
            == ImagePullPolicy.IF_NOT_PRESENT
        )

    def test_round_trip_conversion(self):
        """Test round-trip conversion maintains consistency."""
        for enum_value in [
            ImagePullPolicy.ALWAYS,
            ImagePullPolicy.NEVER,
            ImagePullPolicy.IF_NOT_PRESENT,
        ]:
            # Test with internal value
            result = ImagePullPolicy.from_user_input(enum_value.value)
            assert result == enum_value

            # Test with display value
            display = enum_value.to_display()
            result = ImagePullPolicy.from_user_input(display)
            assert result == enum_value

    def test_ui_friendly_aliases(self):
        """Test UI-friendly aliases work correctly."""
        # "missing" should map to IF_NOT_PRESENT
        result = ImagePullPolicy.from_user_input("missing")
        assert result == ImagePullPolicy.IF_NOT_PRESENT
        assert result.to_display() == "missing"
        assert result.to_k8s() == "IfNotPresent"

    def test_case_insensitive_handling(self):
        """Test case-insensitive handling works for all formats."""
        test_cases = [
            ("always", "ALWAYS", "Always", "aLwAyS"),
            ("never", "NEVER", "Never", "nEvEr"),
            ("missing", "MISSING", "Missing", "mIsSiNg"),
        ]

        for case_variants in test_cases:
            expected = ImagePullPolicy.from_user_input(case_variants[0])
            for variant in case_variants:
                assert ImagePullPolicy.from_user_input(variant) == expected

    def test_enum_choices_method(self):
        """Test the choices() method works for Django model fields."""
        choices = ImagePullPolicy.choices()
        expected = (
            ("Always", "Always"),
            ("Never", "Never"),
            ("IfNotPresent", "IfNotPresent"),
        )
        assert choices == expected

    def test_enum_values_method(self):
        """Test the values() method works for validation."""
        values = ImagePullPolicy.values()
        expected = ("Always", "Never", "IfNotPresent")
        assert values == expected
