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

"""Unit tests for credential type validation-pattern helpers.

Covers the defensive / edge-case branches in
``aap_eda.api.serializers.credential_type._with_field_patterns``
and ``CredentialTypeSerializer.to_representation``, as well as the
``inject_clean_text_patterns`` call in
``aap_eda.api.metadata.EDAMetadata.get_field_info``.

These are pure unit tests that mock the DAB imports so they run
regardless of whether ``ansible_base.lib.metadata`` exposes the
validation helpers in the current environment.
"""

from unittest import mock

# ---------------------------------------------------------------
# _with_field_patterns
# ---------------------------------------------------------------
FAKE_PATTERN = {
    "pattern": r"^[\w\-\.]+$",
    "description": "Only word characters, hyphens and dots.",
}


class TestWithFieldPatterns:
    """Exercise every branch of _with_field_patterns."""

    @staticmethod
    def _call_with_patterns(inputs, tier2_pattern=FAKE_PATTERN):
        """Import and call _with_field_patterns with mocked deps."""
        with mock.patch(
            "aap_eda.api.serializers.credential_type.get_tier2_pattern",
            return_value=tier2_pattern,
        ):
            from aap_eda.api.serializers.credential_type import (
                _with_field_patterns,
            )

            return _with_field_patterns(inputs)

    def test_string_field_gets_pattern(self):
        """Non-secret string field should gain pattern keys."""
        inputs = {
            "fields": [
                {
                    "id": "host",
                    "label": "Host",
                    "type": "string",
                },
            ],
        }
        result = self._call_with_patterns(inputs)
        field = result["fields"][0]
        assert field["pattern"] == FAKE_PATTERN["pattern"]
        assert field["pattern_description"] == FAKE_PATTERN["description"]

    def test_secret_field_excluded(self):
        """Secret fields must NOT get a pattern."""
        inputs = {
            "fields": [
                {
                    "id": "token",
                    "label": "Token",
                    "type": "string",
                    "secret": True,
                },
            ],
        }
        result = self._call_with_patterns(inputs)
        field = result["fields"][0]
        assert "pattern" not in field
        assert "pattern_description" not in field

    def test_non_string_type_excluded(self):
        """Fields with type != 'string' must NOT get a pattern."""
        inputs = {
            "fields": [
                {
                    "id": "verify",
                    "label": "Verify SSL",
                    "type": "boolean",
                },
            ],
        }
        result = self._call_with_patterns(inputs)
        field = result["fields"][0]
        assert "pattern" not in field

    def test_non_dict_field_item_unchanged(self):
        """Non-dict items in the fields list pass through as-is."""
        inputs = {
            "fields": ["not-a-dict"],
        }
        result = self._call_with_patterns(inputs)
        assert result["fields"] == ["not-a-dict"]

    def test_fields_key_missing(self):
        """Inputs without a 'fields' key are returned unchanged."""
        inputs = {"required": ["host"]}
        result = self._call_with_patterns(inputs)
        assert result is inputs

    def test_fields_not_a_list(self):
        """Inputs where 'fields' is not a list are returned unchanged."""
        inputs = {"fields": "bad-value"}
        result = self._call_with_patterns(inputs)
        assert result is inputs

    def test_get_tier2_pattern_none(self):
        """When get_tier2_pattern is None, inputs are returned as-is."""
        inputs = {
            "fields": [
                {"id": "host", "label": "Host", "type": "string"},
            ],
        }
        with mock.patch(
            "aap_eda.api.serializers.credential_type.get_tier2_pattern",
            None,
        ):
            from aap_eda.api.serializers.credential_type import (
                _with_field_patterns,
            )

            result = _with_field_patterns(inputs)
        assert result is inputs

    def test_extra_keys_preserved(self):
        """Extra top-level keys in inputs dict are preserved."""
        inputs = {
            "fields": [
                {"id": "host", "label": "Host", "type": "string"},
            ],
            "required": ["host"],
        }
        result = self._call_with_patterns(inputs)
        assert result["required"] == ["host"]
        assert result["fields"][0]["pattern"] == FAKE_PATTERN["pattern"]

    def test_mixed_field_types(self):
        """String, secret, and boolean fields in a single schema."""
        inputs = {
            "fields": [
                {"id": "user", "label": "User", "type": "string"},
                {
                    "id": "pass",
                    "label": "Pass",
                    "type": "string",
                    "secret": True,
                },
                {"id": "ssl", "label": "SSL", "type": "boolean"},
            ],
        }
        result = self._call_with_patterns(inputs)

        user_field = result["fields"][0]
        assert user_field["pattern"] == FAKE_PATTERN["pattern"]
        assert (
            user_field["pattern_description"] == FAKE_PATTERN["description"]
        )

        pass_field = result["fields"][1]
        assert "pattern" not in pass_field

        ssl_field = result["fields"][2]
        assert "pattern" not in ssl_field


# ---------------------------------------------------------------
# CredentialTypeSerializer.to_representation
# ---------------------------------------------------------------
class TestToRepresentation:
    """Cover all branches of CredentialTypeSerializer.to_representation."""

    @staticmethod
    def _make_serializer_and_call(
        instance_inputs,
        validation_enabled_val=True,
        validation_enabled_is_none=False,
    ):
        """Build a mock instance and call to_representation.

        Uses mock.patch to control the module-level ``validation_enabled``
        and ``_with_field_patterns`` dependencies.
        """
        # Build a minimal mock instance that super().to_representation will
        # turn into a dict with an "inputs" key.
        fake_data = {
            "id": 1,
            "name": "test",
            "inputs": instance_inputs,
        }

        ve = None if validation_enabled_is_none else (
            mock.Mock(return_value=validation_enabled_val)
        )

        with mock.patch(
            "aap_eda.api.serializers.credential_type.validation_enabled",
            ve,
        ), mock.patch(
            "aap_eda.api.serializers.credential_type._with_field_patterns",
            side_effect=lambda i: {**i, "_decorated": True},
        ) as mock_wfp, mock.patch.object(
            # Bypass the real ORM-backed super().to_representation
            __import__(
                "aap_eda.api.serializers.credential_type",
                fromlist=["CredentialTypeSerializer"],
            ).CredentialTypeSerializer.__bases__[0],
            "to_representation",
            return_value=fake_data,
        ):
            from aap_eda.api.serializers.credential_type import (
                CredentialTypeSerializer,
            )

            serializer = CredentialTypeSerializer()
            result = serializer.to_representation(mock.Mock())
        return result, mock_wfp

    def test_validation_enabled_and_inputs_dict(self):
        """When enabled + dict inputs, _with_field_patterns is called."""
        inputs = {"fields": []}
        result, mock_wfp = self._make_serializer_and_call(inputs)
        mock_wfp.assert_called_once_with(inputs)
        assert result["inputs"]["_decorated"] is True

    def test_validation_enabled_is_none(self):
        """When validation_enabled is None, skip pattern injection."""
        inputs = {"fields": []}
        result, mock_wfp = self._make_serializer_and_call(
            inputs, validation_enabled_is_none=True
        )
        mock_wfp.assert_not_called()
        assert result["inputs"] is inputs

    def test_validation_disabled(self):
        """When validation_enabled() returns False, skip injection."""
        inputs = {"fields": []}
        result, mock_wfp = self._make_serializer_and_call(
            inputs, validation_enabled_val=False
        )
        mock_wfp.assert_not_called()
        assert result["inputs"] is inputs

    def test_inputs_not_dict(self):
        """When inputs is not a dict (e.g. None), skip injection."""
        result, mock_wfp = self._make_serializer_and_call(
            None, validation_enabled_val=True
        )
        mock_wfp.assert_not_called()
        assert result["inputs"] is None

    def test_inputs_is_string(self):
        """When inputs is a string, skip injection."""
        result, mock_wfp = self._make_serializer_and_call(
            "not-a-dict", validation_enabled_val=True
        )
        mock_wfp.assert_not_called()
        assert result["inputs"] == "not-a-dict"


# ---------------------------------------------------------------
# EDAMetadata.get_field_info – inject_clean_text_patterns call
# ---------------------------------------------------------------
class TestEDAMetadataGetFieldInfo:
    """Cover the inject_clean_text_patterns branch in get_field_info."""

    def test_inject_called_when_available(self):
        """When inject_clean_text_patterns is not None it must be called."""
        fake_inject = mock.Mock(
            return_value={"type": "string", "pattern": "^.*$"}
        )
        fake_field = mock.Mock(spec=[])

        with mock.patch(
            "aap_eda.api.metadata.inject_clean_text_patterns",
            fake_inject,
        ), mock.patch(
            "aap_eda.api.metadata.metadata.SimpleMetadata.get_field_info",
            return_value={"type": "string"},
        ):
            from aap_eda.api.metadata import EDAMetadata

            meta = EDAMetadata()
            result = meta.get_field_info(fake_field)

        fake_inject.assert_called_once_with(
            fake_field, {"type": "string"}
        )
        assert result["pattern"] == "^.*$"

    def test_inject_skipped_when_none(self):
        """When inject_clean_text_patterns is None, skip it."""
        fake_field = mock.Mock(spec=[])

        with mock.patch(
            "aap_eda.api.metadata.inject_clean_text_patterns",
            None,
        ), mock.patch(
            "aap_eda.api.metadata.metadata.SimpleMetadata.get_field_info",
            return_value={"type": "string"},
        ):
            from aap_eda.api.metadata import EDAMetadata

            meta = EDAMetadata()
            result = meta.get_field_info(fake_field)

        assert result == {"type": "string"}
