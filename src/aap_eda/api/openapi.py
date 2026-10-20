from ansible_base.api_documentation.clean_text_schema_hooks import (
    inject_clean_text_pattern_components as _dab_inject,
)
from django.conf import settings
from drf_spectacular.authentication import SessionScheme as _SessionScheme

_CREDENTIAL_TYPE_SCHEMAS_WITH_INPUTS = frozenset(
    {
        "CredentialType",
        "CredentialTypeCreate",
        "PatchedCredentialTypeCreate",
    }
)

_INPUTS_DESCRIPTION_NOTE = (
    "When ENHANCED_INPUT_VALIDATION_ENABLED is on, non-secret string "
    "entries in fields[] and metadata[] may include optional pattern, "
    "patternDescription, and flags (Tier 2). Secret and non-string fields "
    "omit them. Requiredness is expressed via inputs.required, not per-field "
    "required."
)


def _credential_type_inputs_openapi_schema(
    existing_inputs_prop=None, *, include_structure
):
    """Return the OpenAPI schema for ``CredentialType.inputs``.

    The read schema documents the conventional field-catalog structure. The
    create and update schemas remain free-form JSON because
    ``openapi-python-client`` generates a model for object schemas with
    properties, which is incompatible with the dynamic credential-type input
    dictionaries accepted by the API.
    """
    if not isinstance(existing_inputs_prop, dict):
        existing_inputs_prop = {}
    base_description = existing_inputs_prop.get("description") or (
        "Credential type input schema: fields[], optional "
        "metadata[], and required ids."
    )
    description = (
        base_description
        if _INPUTS_DESCRIPTION_NOTE in base_description
        else f"{base_description} {_INPUTS_DESCRIPTION_NOTE}".strip()
    )
    schema = {
        "description": description,
        "additionalProperties": True,
    }
    if not include_structure:
        schema["example"] = {
            "fields": [
                {
                    "id": "username",
                    "type": "string",
                    "label": "Username",
                }
            ],
            "required": ["username"],
        }
        return schema

    field_item_ref = {
        "$ref": "#/components/schemas/CleanTextNestedStringField",
    }
    return {
        **schema,
        "type": "object",
        "properties": {
            "fields": {
                "type": "array",
                "description": (
                    "Input field catalog. Dynamic per credential type."
                ),
                "items": field_item_ref,
            },
            "required": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional list of field ids that are required."
                ),
            },
            "metadata": {
                "type": "array",
                "description": (
                    "Optional. Present on some external-secret "
                    "credential types; same item shape as fields[]."
                ),
                "items": field_item_ref,
            },
        },
    }


def inject_clean_text_pattern_components(
    result,
    generator,
    request,
    public,
):  # noqa: ARG001
    """Register DAB CleanText components and document CredentialType.inputs."""
    result = _dab_inject(result, generator, request, public)

    schemas = result.get("components", {}).get("schemas", {})
    for schema_name in _CREDENTIAL_TYPE_SCHEMAS_WITH_INPUTS:
        schema = schemas.get(schema_name)
        if not isinstance(schema, dict):
            continue
        props = schema.setdefault("properties", {})
        props["inputs"] = _credential_type_inputs_openapi_schema(
            props.get("inputs"),
            include_structure=schema_name == "CredentialType",
        )

    return result


def preprocess_filter_api_routes(endpoints):
    api_path = f"/{settings.API_PREFIX}"
    return [
        (path, path_regex, method, callback)
        for path, path_regex, method, callback in endpoints
        if path.startswith(api_path)
    ]


def remove_optional_rule_engine_credential_id(
    result, generator, request, public
):
    """Make the rule engine credential field optional in read schemas."""
    del generator, request, public

    schemas = result.get("components", {}).get("schemas", {})
    for schema_name in ("ActivationList", "ActivationRead"):
        schema = schemas.get(schema_name)
        if not schema or "required" not in schema:
            continue

        required = schema["required"]
        schema["required"] = [
            field for field in required if field != "rule_engine_credential_id"
        ]
        if not schema["required"]:
            del schema["required"]

    return result


class SessionScheme(_SessionScheme):
    target_class = "aap_eda.api.authentication.SessionAuthentication"
