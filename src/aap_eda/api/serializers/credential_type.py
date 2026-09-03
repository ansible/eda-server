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

from ansible_base.lib.metadata import get_tier2_pattern, validation_enabled
from ansible_base.lib.serializers.mixins import CleanTextMixin
from rest_framework import serializers

from aap_eda.core import models, validators
from aap_eda.core.utils.credentials import validate_injectors


class CredentialTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CredentialType
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
            "managed",
        ]
        fields = [
            "name",
            "namespace",
            "kind",
            "description",
            "inputs",
            "injectors",
            *read_only_fields,
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        inputs = data.get("inputs")
        if validation_enabled() and isinstance(inputs, dict):
            data["inputs"] = _with_field_patterns(inputs)
        return data


python
def _with_field_patterns(inputs: dict) -> dict:
    """Return a copy of the inputs schema with patterns for string fields.

    CleanTextMixin (from DAB) enforces free-text validation rules on
    serializer string fields at write time (when the ENHANCED_INPUT_VALIDATION_ENABLED setting is turned on).  Only non-secret "string"
    sub-fields get a pattern here, since those are the only ones its
    JSON sub-key validation applies to; secret and boolean fields are
    left untouched.
    """
    fields = inputs.get("fields")
    if not isinstance(fields, list):
        return inputs

    pattern = get_tier2_pattern()
    new_fields = [
        {
            **field,
            "pattern": pattern["pattern"],
            "pattern_description": pattern["description"],
        }
        if isinstance(field, dict)
        and field.get("type") == "string"
        and not field.get("secret")
        else field
        for field in fields
    ]
    return {**inputs, "fields": new_fields}

class CredentialTypeCreateSerializer(
    CleanTextMixin, serializers.ModelSerializer
):
    # injectors commonly contain Jinja2 template syntax, so it is excluded
    # from free-text checks.
    excluded_fields = frozenset({"injectors"})

    inputs = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Inputs of the credential type",
        validators=[validators.check_if_schema_valid],
    )
    injectors = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Injectors of the credential type",
    )

    def validate(self, data):
        injectors = data.get("injectors")
        inputs = data.get("inputs")

        if self.partial:
            inputs = inputs or self.instance.inputs

        if injectors or injectors == {}:
            errors = validate_injectors(inputs, injectors)
            if bool(errors):
                raise serializers.ValidationError(errors)

        return data

    class Meta:
        model = models.CredentialType
        fields = [
            "name",
            "description",
            "inputs",
            "injectors",
        ]


class CredentialTypeRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CredentialType
        fields = ["id", "name", "namespace", "kind"]


class CredentialTypeTestSerializer(serializers.ModelSerializer):
    inputs = serializers.JSONField(
        required=True,
        help_text="Inputs of the credential type for test",
    )
    metadata = serializers.JSONField(
        required=False,
        help_text="Metadata of the credential type for testing",
    )

    def validate(self, data):
        metadata = data.get("metadata", {})
        inputs = data.get("inputs")

        validators.check_credential_test_data(self.instance, inputs, metadata)
        return data

    class Meta:
        model = models.CredentialType
        fields = [
            "inputs",
            "metadata",
        ]
