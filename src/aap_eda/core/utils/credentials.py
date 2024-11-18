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

import re
import tempfile

import gnupg
import jinja2
import validators
import yaml
from django.core.exceptions import ValidationError
from jinja2.nativetypes import NativeTemplate
from rest_framework import serializers

from aap_eda.api.constants import EDA_SERVER_VAULT_LABEL
from aap_eda.core.utils.awx import validate_ssh_private_key

ENCRYPTED_STRING = "$encrypted$"
EDA_PREFIX = "EDA_"
SUPPORTED_KEYS_IN_INJECTORS = ["extra_vars"]
PROTECTED_PASSPHRASE_ERROR = (
    "The key is passphrase protected, please provide passphrase."
)


class InjectorMissingKeyException(Exception):
    pass


def inputs_to_display(schema: dict, inputs: str) -> dict:
    secret_fields = get_secret_fields(schema)
    decoded_inputs = inputs_from_store(inputs)
    result = {}

    for key in decoded_inputs.keys():
        if key in secret_fields:
            if decoded_inputs[key]:
                result[key] = ENCRYPTED_STRING
        else:
            result[key] = decoded_inputs[key]

    return result


def get_secret_fields(schema: dict) -> list[str]:
    return [
        field["id"]
        for field in schema["fields"]
        if "secret" in field and bool(field["secret"])
    ]


def inputs_to_store(inputs: dict, old_inputs_str: str = None) -> str:
    return yaml.dump(inputs_to_store_dict(inputs, old_inputs_str))


def inputs_to_store_dict(inputs: dict, old_inputs_str: str = None) -> dict:
    old_inputs = (
        inputs_from_store(old_inputs_str.get_secret_value())
        if old_inputs_str
        else {}
    )

    old_inputs.update(
        (k, inputs[k]) for k, v in inputs.items() if v != ENCRYPTED_STRING
    )
    return old_inputs


def inputs_from_store(inputs: str) -> dict:
    return yaml.safe_load(inputs)


def validate_inputs(schema: dict, inputs: dict) -> dict:
    """Validate user inputs against credential schema.

    Sample output:
    {
        "password": ["Cannot be blank"]
        "verify_ssl": ["Must be a boolean"]
        "region": ["Must be one of the choices"]
    }

    Return an empty dict if no error.
    """
    errors = {}
    required_fields = schema.get("required", [])

    schema_fields = schema.get("fields", [])
    schema_keys = {field["id"] for field in schema_fields}
    invalid_keys = inputs.keys() - schema_keys
    if bool(invalid_keys):
        errors["inputs"] = (
            f"Input keys {invalid_keys} are not defined "
            f"in the schema. Allowed keys are: {schema_keys}"
        )

        return errors

    for data in schema_fields:
        field = data["id"]
        required = field in required_fields
        default = data.get("default")
        user_input = inputs.get(field)
        display_field = f"inputs.{field}"

        if user_input is None:
            if default:
                inputs[field] = default
            if required and not default:
                errors[display_field] = ["Cannot be blank"]
                continue
        else:
            if required and len(user_input.strip()) == 0:
                errors[display_field] = ["Cannot be blank"]
                continue

        if data.get("format") and user_input:
            result = _validate_format(
                schema=schema,
                data_type=data.get("format"),
                data=user_input,
                inputs=inputs,
            )
            if bool(result):
                if PROTECTED_PASSPHRASE_ERROR in result:
                    errors["inputs.ssh_key_unlock"] = result
                else:
                    errors[display_field] = result

        if (field == "host") and user_input:
            result = _validate_host_name(user_input)
            if bool(result):
                errors[display_field] = result

        if field == "gpg_public_key":
            result = _validate_gpg_public_key(user_input)
            if bool(result):
                errors[display_field] = result

        if data.get("type") == "boolean":
            if user_input and not isinstance(user_input, bool):
                errors[display_field] = ["Must be a boolean"]
            continue

        choices = data.get("choices")
        if choices and user_input and user_input not in choices:
            errors[display_field] = [f"Must be one of the choices: {choices}"]
            continue

    return errors


def validate_schema(schema: dict) -> list[str]:
    """Validate a credential schema.

    Sample output:
    [
        "label must exist and be a string",
        "type must be either string or boolean"
    ]

    Return an empty list if no errors.
    """
    errors = []
    if not isinstance(schema, dict):
        errors.append("schema must be in dict format")
        return errors

    fields = schema.get("fields")

    if not fields:
        errors.append("'fields' must exist and non empty")
    elif not isinstance(fields, list):
        errors.append("'fields' must be a list")
    else:
        id_fields = _get_id_fields(schema)
        duplicates = []
        uniqs = []
        for id in id_fields:
            if id in uniqs:
                duplicates.append(id)
            else:
                uniqs.append(id)

        if len(duplicates) > 0:
            errors.append(f"Duplicate fields: {set(duplicates)} found")

        for id in id_fields:
            if id.upper().startswith(EDA_PREFIX):
                errors.append(f"{id} should not start with {EDA_PREFIX}")

            if not bool(re.match(r"^\w+$", id)):
                errors.append(
                    f"{id} can only contain alphanumeric and "
                    "underscore characters"
                )

        for field in fields:
            for option in ["id", "label"]:
                value = field.get(option)
                if not value or not isinstance(value, str):
                    errors.append(f"{option} must exist and be a string")

            field_type = field.get("type")
            if field_type and field_type not in ["string", "boolean"]:
                errors.append("type must be either string or boolean")

            choices = field.get("choices")
            if choices:
                if not isinstance(choices, list) or any(
                    not isinstance(choice, str) for choice in choices
                ):
                    errors.append("choices must be a list of strings")

            for option in ["secret", "multiline"]:
                value = field.get(option)
                if value is not None and not isinstance(value, bool):
                    errors.append(f"{option} must be a boolean")

            for option in ["help_text", "format"]:
                value = field.get(option)
                if value is not None and not isinstance(value, str):
                    errors.append(f"{option} must be a string")

    required_fields = schema.get("required")
    if required_fields:
        if not isinstance(required_fields, list):
            errors.append("required must be a list of strings")
        else:
            for field_id in required_fields:
                if field_id not in id_fields:
                    errors.append(f"required field {field_id} does not exist")

    return errors


def validate_injectors(schema: dict, injectors: dict) -> dict:
    errors = []

    if not isinstance(injectors, dict):
        errors.append("Injectors must be in Key-Value pairs format")

    if not any(
        support_key in injectors.keys()
        for support_key in SUPPORTED_KEYS_IN_INJECTORS
    ):
        errors.append(
            "Injectors must have keys defined in"
            f" {SUPPORTED_KEYS_IN_INJECTORS}"
        )

    context = _default_context(schema)

    for field in SUPPORTED_KEYS_IN_INJECTORS:
        input_data = injectors.get(field)
        if not input_data:
            continue

        if not isinstance(input_data, dict):
            errors.append(f"{field} must be a dict type")
            continue

        for k, v in input_data.items():
            try:
                if isinstance(v, str):
                    _check_jinja_string(v, context)
            except InjectorMissingKeyException as e:
                errors.append(
                    f"Injector key: {k} has a value which refers to an"
                    f" undefined key error: {e}"
                )

    return {"injectors": errors} if bool(errors) else {}


def validate_host_name(host: str) -> None:
    errors = _validate_host_name(host)
    if bool(errors):
        raise serializers.ValidationError(f"invalid host name: {host}")


def _validate_host_name(host: str) -> list[str]:
    errors = []

    # Yes, validators returns (not throws) an exception if the argument doesn't
    # pass muster (it returns True otherwise).  Consequently we have to check
    # the class of the return to know what happened and if it's not validators'
    # validation exception raise whatever the heck it is.
    validity = validators.hostname(host)
    if isinstance(validity, Exception):
        if not isinstance(validity, validators.ValidationError):
            raise
        errors.append("Host format invalid")
    return errors


def _get_id_fields(schema: dict) -> list[str]:
    fields = schema.get("fields", [])

    return [field.get("id") for field in fields if field.get("id")]


def _default_context(schema: dict) -> dict:
    results = {}

    fields = schema.get("fields", [])

    for field in fields:
        field_type = field.get("type")
        if field_type == "boolean":
            results[field["id"]] = True
        else:
            results[field["id"]] = ""

        default = field.get("default")
        if default:
            results[field["id"]] = default

        choices = field.get("choices")
        if choices:
            if isinstance(choices, list):
                results[field["id"]] = choices[0]

    return results


def _check_jinja_string(value: str, context: dict) -> str:
    try:
        if "{{" in value and "}}" in value:
            result = NativeTemplate(
                value, undefined=jinja2.StrictUndefined
            ).render(context)
            if isinstance(result, jinja2.runtime.StrictUndefined):
                raise InjectorMissingKeyException(f"{value} is undefined")
    except jinja2.exceptions.UndefinedError:
        raise InjectorMissingKeyException(f"{value} is undefined")


def _validate_format(
    schema: dict, data_type: str, data: str, inputs: dict
) -> list[str]:
    errors = []

    if data_type == "vault_id":
        return _validate_vault_id(data)

    elif data_type == "ssh_private_key":
        return _validate_ssh_key(schema, data, inputs)

    return errors


def _validate_vault_id(data: str) -> list[str]:
    errors = []

    if not bool(re.match(r"^\w+$", data)):
        errors.append(
            "vault_id can only contain alphanumeric and "
            "underscore characters"
        )

    if data == EDA_SERVER_VAULT_LABEL:
        errors.append(f"vault_id can not be {EDA_SERVER_VAULT_LABEL}")

    return errors


def _validate_ssh_key(schema: dict, data: str, inputs: dict) -> list[str]:
    errors = []
    try:
        results = validate_ssh_private_key(data)

        if results[0]["type"] != "PRIVATE KEY":
            errors.append("Data is not a private key")

        id_fields = _get_id_fields(schema)

        if "ssh_key_unlock" in id_fields and "ssh_key_data" in id_fields:
            if results[0]["key_enc"] and not inputs.get("ssh_key_unlock"):
                errors.append(PROTECTED_PASSPHRASE_ERROR)
    except ValidationError as e:
        errors.append(str(e))

    return errors


def _validate_gpg_public_key(key_data: str) -> list[str]:
    errors = []

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            gpg = gnupg.GPG(gnupghome=temp_dir)
            import_result = gpg.import_keys(key_data)
            error = import_result.stderr

            if import_result.returncode != 0:
                errors.append(f"No valid GPG data found: {error}")
                return errors

            if import_result.sec_read > 0:
                errors.append(f"Key is not a public key: {error}")
        except Exception as e:
            msg = f"Failed to validate GPG key: {str(e)}"
            errors.append(msg)

    return errors
