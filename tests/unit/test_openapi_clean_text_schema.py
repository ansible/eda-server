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

"""Unit tests for CleanText / credential-type OpenAPI postprocessing."""

from aap_eda.api.openapi import inject_clean_text_pattern_components


def test_inject_clean_text_pattern_components_documents_credential_type_inputs():
    result = {
        "components": {
            "schemas": {
                "CredentialType": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "inputs": {},
                        "injectors": {},
                    },
                },
                "CredentialTypeCreate": {
                    "properties": {
                        "inputs": {
                            "description": "Inputs of the credential type",
                        },
                    },
                },
            },
        },
    }
    inject_clean_text_pattern_components(result, None, None, None)

    schemas = result["components"]["schemas"]
    assert "CleanTextNestedStringField" in schemas

    inputs = schemas["CredentialType"]["properties"]["inputs"]
    assert inputs["type"] == "object"
    assert "fields" in inputs["properties"]
    assert inputs["properties"]["fields"]["items"] == {
        "$ref": "#/components/schemas/CleanTextNestedStringField",
    }
    assert "metadata" in inputs["properties"]
    assert "required" in inputs["properties"]
    assert inputs["additionalProperties"] is True

    nested = schemas["CleanTextNestedStringField"]["properties"]
    assert "patternDescription" in nested
    assert "normalize" not in nested

    create_inputs = schemas["CredentialTypeCreate"]["properties"]["inputs"]
    assert create_inputs["properties"]["fields"]["items"]["$ref"].endswith(
        "CleanTextNestedStringField"
    )
