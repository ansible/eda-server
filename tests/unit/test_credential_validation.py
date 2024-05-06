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
from pathlib import Path

import pytest

from aap_eda.core.utils.credentials import (
    PROTECTED_PASSPHRASE_ERROR,
    SUPPORTED_KEYS_IN_INJECTORS,
    validate_injectors,
    validate_inputs,
    validate_schema,
)

DATA_DIR = Path(__file__).parent / "data"


def test_validate_schema():
    bad_schema_format = (
        {
            "id": "username",
            "label": "Username",
            "type": "string",
        },
    )

    errors = validate_schema(bad_schema_format)
    assert "schema must be in dict format" in errors

    no_fields_schema = {
        "id": "username",
        "label": "Username",
        "type": "string",
    }

    errors = validate_schema(no_fields_schema)
    assert "'fields' must exist and non empty" in errors

    eda_prefix_id_schema = {
        "fields": [
            {
                "id": "eda_illegal",
                "label": "Username",
                "type": "string",
            },
            {
                "id": "legal",
                "label": "EDA_Username",
                "type": "string",
            },
        ],
    }

    errors = validate_schema(eda_prefix_id_schema)

    assert (
        f"{eda_prefix_id_schema['fields'][0]['id']} should not start with EDA_"
        in errors
    )

    illegal_char_schema = {
        "fields": [
            {
                "id": "illegal++",
                "label": "Username",
                "type": "string",
            },
            {
                "id": "-illegal",
                "label": "Username",
                "type": "string",
            },
        ],
    }

    errors = validate_schema(illegal_char_schema)

    assert (
        f"{illegal_char_schema['fields'][0]['id']} can only contain "
        "alphanumeric and underscore characters" in errors
    )

    missing_field_schemas = {
        "label": {
            "fields": [
                {
                    "id": "username",
                    "type": "string",
                }
            ]
        },
        "id": {
            "fields": [
                {
                    "label": "Username",
                    "type": "string",
                }
            ]
        },
    }
    for missing in missing_field_schemas:
        errors = validate_schema(missing_field_schemas[missing])

        assert f"{missing} must exist and be a string" in errors

    choices_field_schemas = {
        "not_a_list": {
            "fields": [
                {
                    "id": "username",
                    "label": "Username",
                    "type": "string",
                    "choices": "not a list",
                }
            ]
        },
        "list_item_not_a_string": {
            "fields": [
                {
                    "id": "username",
                    "label": "Username",
                    "type": "string",
                    "choices": [1, 2, 3],
                }
            ]
        },
    }

    for choice in choices_field_schemas:
        errors = validate_schema(choices_field_schemas[choice])

        assert "choices must be a list of strings" in errors

    bool_field_schemas = {
        "secret": {
            "fields": [
                {
                    "id": "username",
                    "label": "Username",
                    "type": "string",
                    "secret": "secret",
                }
            ]
        },
        "multiline": {
            "fields": [
                {
                    "id": "username",
                    "label": "Username",
                    "type": "string",
                    "multiline": "multiline",
                }
            ]
        },
    }

    for field in bool_field_schemas:
        errors = validate_schema(bool_field_schemas[field])

        assert f"{field} must be a boolean" in errors

    string_field_schemas = {
        "help_text": {
            "fields": [
                {
                    "id": "username",
                    "label": "Username",
                    "type": "string",
                    "help_text": {"a": "b"},
                }
            ]
        },
        "format": {
            "fields": [
                {
                    "id": "username",
                    "label": "Username",
                    "type": "string",
                    "format": {"a": "b"},
                }
            ]
        },
    }

    for field in string_field_schemas:
        errors = validate_schema(string_field_schemas[field])

        assert f"{field} must be a string" in errors

    bad_required_field_schemas = {
        "fields": [
            {
                "id": "username",
                "label": "Username",
                "type": "string",
            }
        ],
        "required": "not a list",
    }

    errors = validate_schema(bad_required_field_schemas)
    assert "required must be a list of strings" in errors

    missing_fields = ["a", "b"]
    missing_required_field_schemas = {
        "fields": [
            {
                "id": "username",
                "label": "Username",
                "type": "string",
            }
        ],
        "required": missing_fields,
    }

    errors = validate_schema(missing_required_field_schemas)

    for field in missing_fields:
        assert f"required field {field} does not exist" in errors

    required_field_schemas = {
        "fields": [
            {
                "id": "host",
                "label": "Authentication URL",
                "type": "string",
                "help_text": (
                    "Authentication endpoint for the container registry."
                ),
                "default": "quay.io",
            },
            {"id": "username", "label": "Username", "type": "string"},
            {
                "id": "password",
                "label": "Password or Token",
                "type": "string",
                "secret": True,
                "help_text": ("A password or token used to authenticate with"),
            },
            {
                "id": "verify_ssl",
                "label": "Verify SSL",
                "type": "boolean",
                "default": True,
            },
        ],
        "required": ["host"],
    }

    errors = validate_schema(required_field_schemas)
    assert bool(errors) is False

    duplicate_schema = {
        "fields": [
            {
                "id": "host",
                "label": "Red Hat Ansible Automation Platform",
                "type": "string",
                "help_text": (
                    "Red Hat Ansible Automation Platform base URL"
                    " to authenticate with."
                ),
            },
            {
                "id": "host",
                "label": "Duplicate Red Hat Ansible Automation Platform",
                "type": "string",
            },
        ]
    }

    errors = validate_schema(duplicate_schema)
    assert "Duplicate fields: {'host'} found" in errors


def test_validate_inputs():
    schema = {
        "fields": [
            {
                "id": "host",
                "label": "Red Hat Ansible Automation Platform",
                "type": "string",
                "help_text": (
                    "Red Hat Ansible Automation Platform base URL"
                    " to authenticate with."
                ),
            },
            {
                "id": "username",
                "label": "Username",
                "type": "string",
                "help_text": (
                    "Red Hat Ansible Automation Platform username id"
                    " to authenticate as.This should not be set if"
                    " an OAuth token is being used."
                ),
            },
            {
                "id": "password",
                "label": "Password",
                "type": "string",
                "secret": True,
            },
            {
                "id": "security_protocol",
                "type": "string",
                "label": "Security Protocol",
                "choices": ["SASL_PLAINTEXT", "SASL_SSL", "PLAINTEXT", "SSL"],
            },
            {
                "id": "oauth_token",
                "label": "OAuth Token",
                "type": "string",
                "secret": True,
                "help_text": (
                    "An OAuth token to use to authenticate with."
                    "This should not be set if username/password"
                    " are being used."
                ),
            },
            {
                "id": "verify_ssl",
                "label": "Verify SSL",
                "type": "boolean",
                "secret": False,
                "default": True,
            },
        ],
        "required": ["host"],
    }

    missing_required_inputs = {
        "username": "adam",
        "password": "secret",
    }

    errors = validate_inputs(schema, missing_required_inputs)
    assert "Cannot be blank" in [*errors.values()][0]

    use_default_inputs = {
        "host": "localhost",
        "username": "adam",
        "password": "secret",
    }
    errors = validate_inputs(schema, use_default_inputs)
    assert use_default_inputs["verify_ssl"] is True

    good_boolean_inputs = {
        "host": "localhost",
        "verify_ssl": True,
    }
    errors = validate_inputs(schema, good_boolean_inputs)
    assert errors == {}

    bad_boolean_inputs = {
        "host": "localhost",
        "verify_ssl": "secret",
    }
    errors = validate_inputs(schema, bad_boolean_inputs)
    assert "Must be a boolean" in [*errors.values()][0]

    good_choices_inputs = {
        "host": "localhost",
        "security_protocol": "PLAINTEXT",
    }
    errors = validate_inputs(schema, good_choices_inputs)
    assert errors == {}

    bad_choices_inputs = {
        "host": "localhost",
        "security_protocol": "TEST",
    }
    errors = validate_inputs(schema, bad_choices_inputs)
    assert [*errors.values()][0][0].startswith("Must be one of the choices")


def test_validate_injectors():
    inputs = {
        "fields": [
            {
                "id": "username",
                "label": "Username",
                "type": "string",
                "default": "adam",
            },
        ]
    }

    injectors = {
        "extra_vars": {
            "keyfile": "{{ keyfile  }}",
            "user": "{{ username  }}",
            "certfile": "{{ my_certificate  }}",
        },
    }

    errors = validate_injectors(inputs, injectors)

    assert errors["injectors"] == [
        "Injector key: keyfile has a value which refers to an undefined key "
        "error: {{ keyfile  }} is undefined",
        "Injector key: certfile has a value which refers to an undefined key "
        "error: {{ my_certificate  }} is undefined",
    ]

    good_injectors = {
        "extra_vars": {
            "user": "{{ username  }}",
        },
    }

    errors = validate_injectors(inputs, good_injectors)
    assert errors == {}

    inputs = {"fields": [{"id": "username", "label": "User Name"}]}

    bad_injectors = {"extra_vars": [{"key2": "{{ adam }}"}]}
    errors = validate_injectors(inputs, bad_injectors)
    assert "extra_vars must be a dict type" in errors["injectors"]

    bad_injectors = {"name": "fred"}
    errors = validate_injectors(inputs, bad_injectors)
    assert (
        f"Injectors must have keys defined in {SUPPORTED_KEYS_IN_INJECTORS}"
        in errors["injectors"]
    )

    for key in SUPPORTED_KEYS_IN_INJECTORS:
        valid_injectors = {key: {"name": "fred"}}
        errors = validate_injectors(inputs, valid_injectors)
        assert errors == {}


@pytest.mark.parametrize(
    ("phrase", "key_file", "decision"),
    [
        ("password", DATA_DIR / "demo1", True),
        (None, DATA_DIR / "demo1", False),
        ("password", None, False),
        (None, DATA_DIR / "demo2", True),
    ],
)
def test_validate_ssh_keys(phrase, key_file, decision):
    if key_file:
        with open(key_file) as f:
            data = f.read()
    else:
        data = "dummy data"

    schema = {
        "fields": [
            {
                "id": "ssh_key_data",
                "type": "string",
                "label": "SCM Private Key",
                "format": "ssh_private_key",
                "secret": True,
                "multiline": True,
            },
            {
                "id": "ssh_key_unlock",
                "type": "string",
                "label": "Private Key Passphrase",
                "secret": True,
            },
        ]
    }

    inputs = {"ssh_key_data": data}

    if phrase:
        inputs["ssh_key_unlock"] = phrase

    errors = validate_inputs(schema, inputs)

    if decision:
        assert errors == {}
    else:
        assert bool(errors) is True
        for key, value in errors.items():
            if PROTECTED_PASSPHRASE_ERROR in value:
                assert key == "inputs.ssh_key_unlock"
            else:
                assert key == "inputs.ssh_key_data"


def test_validate_ssh_keys_without_phrase():
    schema = {
        "fields": [
            {
                "id": "ssh_key_data",
                "type": "string",
                "label": "SCM Private Key",
                "format": "ssh_private_key",
                "secret": True,
                "multiline": True,
            },
        ]
    }

    key_file = DATA_DIR / "demo1"

    with open(key_file) as f:
        data = f.read()

    inputs = {"ssh_key_data": data}
    errors = validate_inputs(schema, inputs)
    assert errors == {}


@pytest.mark.parametrize(
    ("key_file", "status_message"),
    [
        (DATA_DIR / "public_key.asc", ""),
        (DATA_DIR / "private_key.asc", "Key is not a public key"),
        (DATA_DIR / "invalid_key.asc", "No valid GPG data found."),
    ],
)
def test_validate_gpg_keys(key_file, status_message):
    with open(key_file) as f:
        data = f.read()

    schema = {
        "fields": [
            {
                "id": "gpg_public_key",
                "label": "GPG Public Key",
                "type": "string",
                "secret": True,
                "multiline": True,
                "help_text": (
                    "GPG Public Key used to validate content signatures."
                ),
            },
        ]
    }
    inputs = {"gpg_public_key": data}

    errors = validate_inputs(schema, inputs)

    assert status_message in errors.get("inputs.gpg_public_key", "")
