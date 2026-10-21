#  Copyright 2026 Red Hat, Inc.
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
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import override_settings

from aap_eda.api.serializers.eda_credential import (
    EdaCredentialUpdateSerializer,
    _InputsGrandfatherInstance,
)
from aap_eda.core.utils.credentials import inputs_to_store
from aap_eda.core.utils.crypto.base import SecretValue

_CLEAN_TEXT_JSON_FIELD = (
    "ansible_base.lib.serializers.mixins."
    "CleanTextMixin._validate_json_field"
)


@pytest.fixture(autouse=True)
def enable_input_validation(settings):
    settings.ENHANCED_INPUT_VALIDATION_ENABLED = True


class TestInputsGrandfatherInstance:
    def test_exposes_decoded_inputs_and_delegates_other_attrs(self):
        inner = SimpleNamespace(name="registry-cred", pk=7)
        decoded = {"username": "{{legacy}}", "host": "quay.io"}
        proxy = _InputsGrandfatherInstance(inner, decoded)

        assert proxy.inputs == decoded
        assert proxy.name == "registry-cred"
        assert proxy.pk == 7


class TestStoredInputsDictForCleanText:
    def test_returns_none_without_instance(self):
        serializer = EdaCredentialUpdateSerializer()
        assert serializer._stored_inputs_dict_for_clean_text() is None

    def test_returns_empty_dict_for_blank_stored_yaml(self):
        serializer = EdaCredentialUpdateSerializer()
        serializer.instance = SimpleNamespace(inputs="  \n")
        assert serializer._stored_inputs_dict_for_clean_text() == {}

    def test_decodes_secret_value_wrapper(self):
        stored = inputs_to_store({"username": "alice", "password": "secret"})
        serializer = EdaCredentialUpdateSerializer()
        serializer.instance = SimpleNamespace(inputs=SecretValue(stored))

        result = serializer._stored_inputs_dict_for_clean_text()
        assert result == {
            "username": "alice",
            "password": "secret",
        }

    @patch(
        "aap_eda.api.serializers.eda_credential.inputs_from_store",
        return_value=None,
    )
    def test_returns_empty_dict_when_decode_yields_none(self, _mock_decode):
        serializer = EdaCredentialUpdateSerializer()
        serializer.instance = SimpleNamespace(inputs="username: alice")

        assert serializer._stored_inputs_dict_for_clean_text() == {}

    @patch(
        "aap_eda.api.serializers.eda_credential.inputs_from_store",
        return_value=["not", "a", "dict"],
    )
    def test_returns_none_when_decode_is_not_dict(self, _mock_decode):
        serializer = EdaCredentialUpdateSerializer()
        serializer.instance = SimpleNamespace(inputs="username: alice")

        assert serializer._stored_inputs_dict_for_clean_text() is None

    @patch(
        "aap_eda.api.serializers.eda_credential.inputs_from_store",
        side_effect=ValueError("bad yaml"),
    )
    def test_returns_none_on_decode_failure(self, _mock_decode):
        serializer = EdaCredentialUpdateSerializer()
        serializer.instance = SimpleNamespace(inputs="username: alice")

        assert serializer._stored_inputs_dict_for_clean_text() is None

    def test_returns_none_on_malformed_stored_yaml(self):
        serializer = EdaCredentialUpdateSerializer()
        serializer.instance = SimpleNamespace(inputs="username: [unclosed")

        assert serializer._stored_inputs_dict_for_clean_text() is None

    def test_returns_none_when_inputs_attribute_missing(self):
        serializer = EdaCredentialUpdateSerializer()
        serializer.instance = SimpleNamespace()

        assert serializer._stored_inputs_dict_for_clean_text() is None


class TestValidateJsonFieldInputsGrandfathering:
    @override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
    def test_skips_proxy_when_stored_inputs_not_decodable(self):
        serializer = EdaCredentialUpdateSerializer()
        serializer.instance = SimpleNamespace(inputs="username: alice")
        serializer.excluded_json_keys = {"inputs": frozenset()}

        with patch.object(
            serializer,
            "_stored_inputs_dict_for_clean_text",
            return_value=None,
        ) as mock_stored:
            errors = serializer._validate_json_field(
                "inputs",
                {"username": "plain-user"},
            )

        mock_stored.assert_called_once()
        assert errors is None

    @override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
    def test_validate_json_field_without_instance_delegates_to_super(self):
        serializer = EdaCredentialUpdateSerializer()

        with patch(_CLEAN_TEXT_JSON_FIELD, return_value=None) as mock_super:
            errors = serializer._validate_json_field(
                "inputs",
                {"username": "plain-user"},
            )

        mock_super.assert_called_once()
        assert errors is None

    @override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
    def test_delegates_non_inputs_fields_to_super(self):
        serializer = EdaCredentialUpdateSerializer()
        serializer.instance = SimpleNamespace(description="unchanged")

        with patch(
            _CLEAN_TEXT_JSON_FIELD,
            return_value={"description": ["blocked"]},
        ) as mock_super:
            errors = serializer._validate_json_field(
                "description",
                "$(rm -rf /)",
            )

        mock_super.assert_called_once_with("description", "$(rm -rf /)")
        assert errors == {"description": ["blocked"]}

    @override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
    def test_restores_instance_after_inputs_validation(self):
        inner = SimpleNamespace(
            name="cred",
            inputs=inputs_to_store({"username": "{{legacy}}"}),
        )
        serializer = EdaCredentialUpdateSerializer()
        serializer.instance = inner

        serializer._validate_json_field(
            "inputs",
            {"username": "{{legacy}}"},
        )

        assert serializer.instance is inner
