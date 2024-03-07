#  Copyright 20244 Red Hat, Inc.
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

import yaml

ENCRYPTED = "$encrypted$"


def inputs_to_display(schema: dict, inputs: str) -> dict:
    secret_fields = get_secret_fields(schema)
    decoded_inputs = inputs_from_store(inputs)

    for key in decoded_inputs.keys():
        if key in secret_fields:
            decoded_inputs[key] = ENCRYPTED

    return decoded_inputs


def get_secret_fields(schema: dict) -> list[str]:
    return [
        field["id"]
        for field in schema["fields"]
        if "secret" in field and bool(field["secret"])
    ]


def inputs_to_store(inputs: dict, old_inputs_str: str = None) -> str:
    old_inputs = (
        inputs_from_store(old_inputs_str.get_secret_value())
        if old_inputs_str
        else {}
    )

    old_inputs.update((k, inputs[k]) for k, v in inputs.items())
    return yaml.dump(old_inputs)


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
    required_fields = schema["required"]
    for field in schema["fields"]:
        field_id = field["id"]
        required = field_id in required_fields
        default = field.get("default")
        user_input = inputs.get(field_id)

        if user_input is None:
            if default:
                inputs[field_id] = default
            elif required:
                errors[field_id] = ["Cannot be blank"]
            continue

        if field.get("type") == "boolean":
            if not isinstance(user_input, bool):
                errors[field_id] = ["Must be a boolean"]
            continue

        choices = field.get("choices")
        if choices and user_input not in choices:
            errors[field_id] = ["Must be one of the choices"]
            continue

        if not isinstance(user_input, str):
            errors[field_id] = ["Must be a string"]
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
    field_ids = []
    fields = schema.get("fields")

    if not fields:
        errors.append("fields must exist and non empty")
    else:
        for field in fields:
            for option in ["id", "label"]:
                value = field.get(option)
                if not value or not isinstance(value, str):
                    errors.append(f"{option} must exist and be a string")
                elif option == "id":
                    field_ids.append(value)

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
                if field_id not in field_ids:
                    errors.append(f"required field {field_id} does not exist")

    return errors
