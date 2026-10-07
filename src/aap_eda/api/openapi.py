from django.conf import settings
from drf_spectacular.authentication import SessionScheme as _SessionScheme


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
