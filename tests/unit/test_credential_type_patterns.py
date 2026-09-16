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

"""Unit tests for validation pattern helpers.

Covers ``aap_eda.api.validation_patterns`` (centralized pattern
injection) and verifies that ``EDAMetadata.get_field_info`` and
``CredentialTypeSerializer.to_representation`` delegate to it
correctly.

These are pure unit tests that mock the DAB imports so they run
regardless of whether ``ansible_base.lib.metadata`` exposes the
validation helpers in the current environment.
"""

import copy
from unittest import mock

FAKE_PATTERN = r"^[\w\-\.]+$"
FAKE_DESCRIPTION = "Only word characters, hyphens and dots."
VP = "aap_eda.api.validation_patterns"


# ---------------------------------------------------------------
# inject_free_text_pattern
# ---------------------------------------------------------------
class TestInjectFreeTextPattern:
    """Exercise every branch of inject_free_text_pattern."""

    @staticmethod
    def _call(field_schema, **kwargs):
        with (
            mock.patch(
                f"{VP}.build_tier2_frontend_pattern",
                return_value=FAKE_PATTERN,
            ),
            mock.patch(
                f"{VP}.enhanced_input_validation_enabled",
                return_value=True,
            ),
        ):
            from aap_eda.api.validation_patterns import (
                inject_free_text_pattern,
            )

            return inject_free_text_pattern(field_schema, **kwargs)

    def test_string_field_gets_pattern(self):
        """Non-secret string field should gain pattern keys."""
        schema = {"id": "host", "type": "string"}
        result = self._call(schema)
        assert result["pattern"] == FAKE_PATTERN
        assert "pattern_description" in result

    def test_secret_field_excluded(self):
        """Secret fields must NOT get a pattern."""
        schema = {
            "id": "token",
            "type": "string",
            "secret": True,
        }
        result = self._call(schema)
        assert "pattern" not in result

    def test_secret_kwarg_excluded(self):
        """The secret keyword argument skips injection."""
        schema = {"id": "token", "type": "string"}
        result = self._call(schema, secret=True)
        assert "pattern" not in result

    def test_boolean_field_excluded(self):
        """Fields with type != 'string' must NOT get a pattern."""
        schema = {"id": "verify", "type": "boolean"}
        result = self._call(schema)
        assert "pattern" not in result

    def test_non_dict_passthrough(self):
        """Non-dict items pass through unchanged."""
        result = self._call("not-a-dict")
        assert result == "not-a-dict"

    def test_default_type_is_string(self):
        """Fields without explicit type default to string."""
        schema = {"id": "host", "label": "Host"}
        result = self._call(schema)
        assert result["pattern"] == FAKE_PATTERN

    def test_disabled_toggle_skips(self):
        """When toggle is off, no pattern is added."""
        with (
            mock.patch(
                f"{VP}.build_tier2_frontend_pattern",
                return_value=FAKE_PATTERN,
            ),
            mock.patch(
                f"{VP}.enhanced_input_validation_enabled",
                return_value=False,
            ),
        ):
            from aap_eda.api.validation_patterns import (
                inject_free_text_pattern,
            )

            schema = {"id": "host", "type": "string"}
            result = inject_free_text_pattern(schema)
            assert "pattern" not in result

    def test_build_tier2_none_skips(self):
        """When build_tier2_frontend_pattern is None, skip."""
        with (
            mock.patch(
                f"{VP}.build_tier2_frontend_pattern",
                None,
            ),
            mock.patch(
                f"{VP}.enhanced_input_validation_enabled",
                return_value=True,
            ),
        ):
            from aap_eda.api.validation_patterns import (
                inject_free_text_pattern,
            )

            schema = {"id": "host", "type": "string"}
            result = inject_free_text_pattern(schema)
            assert "pattern" not in result


# ---------------------------------------------------------------
# inject_patterns_into_field_list — copy-before-mutate
# ---------------------------------------------------------------
class TestInjectPatternsIntoFieldList:
    """Copy-before-mutate and early-return gating."""

    def test_copy_before_mutate(self):
        """Shared dicts must not be mutated in place."""
        original = {"id": "host", "type": "string"}
        fields = [original]

        with (
            mock.patch(
                f"{VP}.build_tier2_frontend_pattern",
                return_value=FAKE_PATTERN,
            ),
            mock.patch(
                f"{VP}.enhanced_input_validation_enabled",
                return_value=True,
            ),
        ):
            from aap_eda.api.validation_patterns import (
                inject_patterns_into_field_list,
            )

            inject_patterns_into_field_list(fields)

        # The list element was replaced (shallow copy)
        assert fields[0] is not original
        assert fields[0]["pattern"] == FAKE_PATTERN
        # Original dict is untouched
        assert "pattern" not in original

    def test_early_return_when_disabled(self):
        """When toggle is off, nothing changes."""
        original = {"id": "host", "type": "string"}
        fields = [original]

        with mock.patch(
            f"{VP}.enhanced_input_validation_enabled",
            return_value=False,
        ):
            from aap_eda.api.validation_patterns import (
                inject_patterns_into_field_list,
            )

            inject_patterns_into_field_list(fields)

        assert fields[0] is original
        assert "pattern" not in original

    def test_non_list_is_noop(self):
        """Non-list arguments are a no-op."""
        with mock.patch(
            f"{VP}.enhanced_input_validation_enabled",
            return_value=True,
        ):
            from aap_eda.api.validation_patterns import (
                inject_patterns_into_field_list,
            )

            # Should not raise
            inject_patterns_into_field_list(None)
            inject_patterns_into_field_list("bad")

    def test_mixed_field_types(self):
        """String, secret, and boolean in a single schema."""
        fields = [
            {"id": "user", "type": "string"},
            {
                "id": "pass",
                "type": "string",
                "secret": True,
            },
            {"id": "ssl", "type": "boolean"},
        ]
        originals = [copy.copy(f) for f in fields]

        with (
            mock.patch(
                f"{VP}.build_tier2_frontend_pattern",
                return_value=FAKE_PATTERN,
            ),
            mock.patch(
                f"{VP}.enhanced_input_validation_enabled",
                return_value=True,
            ),
        ):
            from aap_eda.api.validation_patterns import (
                inject_patterns_into_field_list,
            )

            inject_patterns_into_field_list(fields)

        assert fields[0]["pattern"] == FAKE_PATTERN
        assert "pattern" not in fields[1]
        assert "pattern" not in fields[2]
        # Originals untouched
        for orig in originals:
            assert "pattern" not in orig


# ---------------------------------------------------------------
# inject_top_level_clean_text_patterns
# ---------------------------------------------------------------
class TestInjectTopLevelCleanTextPatterns:
    """Delegation to DAB's inject_clean_text_patterns."""

    def test_delegates_to_dab(self):
        """When DAB helper is available it must be called."""
        fake_inject = mock.Mock(
            return_value={
                "type": "string",
                "pattern": "^.*$",
            }
        )
        with mock.patch(
            f"{VP}._dab_inject_clean_text_patterns",
            fake_inject,
        ):
            from aap_eda.api.validation_patterns import (
                inject_top_level_clean_text_patterns,
            )

            field = mock.Mock()
            result = inject_top_level_clean_text_patterns(
                field, {"type": "string"}
            )

        fake_inject.assert_called_once_with(field, {"type": "string"})
        assert result["pattern"] == "^.*$"

    def test_noop_when_dab_missing(self):
        """When DAB helper is None, return field_info as-is."""
        with mock.patch(
            f"{VP}._dab_inject_clean_text_patterns",
            None,
        ):
            from aap_eda.api.validation_patterns import (
                inject_top_level_clean_text_patterns,
            )

            info = {"type": "string"}
            result = inject_top_level_clean_text_patterns(mock.Mock(), info)

        assert result is info


# ---------------------------------------------------------------
# CredentialTypeSerializer.to_representation delegation
# ---------------------------------------------------------------
class TestToRepresentation:
    """Verify to_representation delegates to validation_patterns."""

    @staticmethod
    def _make_and_call(instance_inputs):
        fake_data = {
            "id": 1,
            "name": "test",
            "inputs": instance_inputs,
        }

        with (
            mock.patch(
                "aap_eda.api.serializers.credential_type"
                ".inject_patterns_into_field_list",
            ) as mock_inject,
            mock.patch.object(
                __import__(
                    "aap_eda.api.serializers.credential_type",
                    fromlist=["CredentialTypeSerializer"],
                ).CredentialTypeSerializer.__bases__[0],
                "to_representation",
                return_value=fake_data,
            ),
        ):
            from aap_eda.api.serializers.credential_type import (
                CredentialTypeSerializer,
            )

            serializer = CredentialTypeSerializer()
            result = serializer.to_representation(mock.Mock())
        return result, mock_inject

    def test_dict_inputs_calls_inject(self):
        """Dict inputs trigger inject_patterns_into_field_list."""
        inputs = {"fields": [{"id": "x", "type": "string"}]}
        result, mock_inject = self._make_and_call(inputs)
        mock_inject.assert_called_once_with(inputs.get("fields"))

    def test_non_dict_inputs_skips(self):
        """When inputs is None, skip injection."""
        result, mock_inject = self._make_and_call(None)
        mock_inject.assert_not_called()

    def test_string_inputs_skips(self):
        """When inputs is a string, skip injection."""
        result, mock_inject = self._make_and_call("not-a-dict")
        mock_inject.assert_not_called()


# ---------------------------------------------------------------
# EDAMetadata.get_field_info delegation
# ---------------------------------------------------------------
class TestEDAMetadataGetFieldInfo:
    """Verify get_field_info delegates to validation_patterns."""

    def test_delegates_to_validation_patterns(self):
        """inject_top_level_clean_text_patterns must be called."""
        fake_inject = mock.Mock(
            return_value={
                "type": "string",
                "pattern": "^.*$",
            }
        )
        fake_field = mock.Mock(spec=[])

        with (
            mock.patch(
                "aap_eda.api.metadata" ".inject_top_level_clean_text_patterns",
                fake_inject,
            ),
            mock.patch(
                "aap_eda.api.metadata"
                ".metadata.SimpleMetadata.get_field_info",
                return_value={"type": "string"},
            ),
        ):
            from aap_eda.api.metadata import EDAMetadata

            meta = EDAMetadata()
            result = meta.get_field_info(fake_field)

        fake_inject.assert_called_once_with(fake_field, {"type": "string"})
        assert result["pattern"] == "^.*$"
