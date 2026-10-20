from aap_eda.api.openapi import remove_optional_rule_engine_credential_id


def test_optional_credential_id_keeps_required_fields():
    schema = {
        "components": {
            "schemas": {
                "ActivationList": {
                    "required": ["name", "rule_engine_credential_id"]
                },
                "ActivationRead": {"required": ["rule_engine_credential_id"]},
            }
        }
    }

    result = remove_optional_rule_engine_credential_id(
        schema, None, None, None
    )

    assert result["components"]["schemas"]["ActivationList"]["required"] == [
        "name"
    ]
    assert "required" not in result["components"]["schemas"]["ActivationRead"]


def test_optional_credential_id_ignores_missing_schemas():
    schema = {
        "components": {
            "schemas": {
                "ActivationRead": {"properties": {}},
            }
        }
    }

    result = remove_optional_rule_engine_credential_id(
        schema, None, None, None
    )

    assert result == schema
