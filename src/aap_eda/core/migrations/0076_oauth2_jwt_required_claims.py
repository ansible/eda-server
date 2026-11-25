"""Add the optional required_claims input to the OAuth2 JWT credential type.

create_initial_data uses get_or_create for managed credential types, so
existing installs need this migration to pick up the new field.

The field definition is intentionally inlined rather than imported so that
future changes to create_initial_data don't alter this migration.
"""

from django.db import migrations

CREDENTIAL_TYPE_NAME = "OAuth2 JWT Event Stream"
FIELD_ID = "required_claims"
INSERT_AFTER_FIELD_ID = "audience"

REQUIRED_CLAIMS_FIELD = {
    "id": FIELD_ID,
    "label": "Required Claims",
    "type": "string",
    "format": "yaml_dict",
    "multiline": True,
    "help_text": (
        "Additional claims that must be present in the JWT, in JSON or "
        "YAML format. Scalar values must match exactly. If the claim in "
        "the token is a list, it must contain the required value (or all "
        "of the required values, if a list is given). Nested objects are "
        "matched recursively. e.g. "
        '{"iss": "https://idp.example.com", "groups": ["eda-senders"]}'
    ),
}

OLD_DESCRIPTION = (
    "Credential for Event Streams that use OAuth2 with JWT. "
    "This needs a JWKS URL which will be used to fetch the "
    "public key and validate the incoming token. If an audience "
    "is specified we will check the audience in the JWT claims."
)
NEW_DESCRIPTION = OLD_DESCRIPTION + (
    " Any required claims specified will also be validated."
)


def add_required_claims(apps, schema_editor):
    credential_type = apps.get_model("core", "CredentialType")  # noqa: N806

    for ctype in credential_type.objects.filter(name=CREDENTIAL_TYPE_NAME):
        fields = ctype.inputs.get("fields", [])
        if any(field.get("id") == FIELD_ID for field in fields):
            continue

        position = len(fields)
        for index, field in enumerate(fields):
            if field.get("id") == INSERT_AFTER_FIELD_ID:
                position = index + 1
                break
        fields.insert(position, dict(REQUIRED_CLAIMS_FIELD))
        ctype.inputs["fields"] = fields

        update_fields = ["inputs"]
        if ctype.description == OLD_DESCRIPTION:
            ctype.description = NEW_DESCRIPTION
            update_fields.append("description")
        ctype.save(update_fields=update_fields)


def remove_required_claims(apps, schema_editor):
    credential_type = apps.get_model("core", "CredentialType")  # noqa: N806

    for ctype in credential_type.objects.filter(name=CREDENTIAL_TYPE_NAME):
        fields = ctype.inputs.get("fields", [])
        ctype.inputs["fields"] = [
            field for field in fields if field.get("id") != FIELD_ID
        ]

        update_fields = ["inputs"]
        if ctype.description == NEW_DESCRIPTION:
            ctype.description = OLD_DESCRIPTION
            update_fields.append("description")
        ctype.save(update_fields=update_fields)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0075_rulebookprocess_activation_job_namespace"),
    ]

    operations = [
        migrations.RunPython(add_required_claims, remove_required_claims),
    ]
