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
import typing
from datetime import datetime, timezone
from typing import Any, Optional

import gnupg
import jinja2
import validators
import yaml
from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.x509.oid import NameOID
from django.core.exceptions import ValidationError
from django.forms import model_to_dict
from django.utils.translation import gettext_lazy as _
from jinja2.nativetypes import NativeTemplate
from rest_framework import serializers

from aap_eda.api.constants import EDA_SERVER_VAULT_LABEL
from aap_eda.core import enums
from aap_eda.core.utils.crypto.base import SecretValue
from aap_eda.core.utils.external_sms import get_external_secrets

if typing.TYPE_CHECKING:
    from aap_eda.core import models

import logging

from aap_eda.core.utils.awx import validate_ssh_private_key

LOGGER = logging.getLogger(__name__)
ENCRYPTED_STRING = "$encrypted$"
EDA_PREFIX = "EDA_"
SUPPORTED_KEYS_IN_INJECTORS = {"env", "extra_vars", "file"}
PROTECTED_PASSPHRASE_ERROR = (
    "The key is passphrase protected, please provide passphrase."
)

RESERVED_EXTRA_VAR_KEYS = {"ansible", "eda"}


class InjectorMissingKeyException(Exception):
    pass


class InjectorInvalidTemplateKey(Exception):
    pass


class InjectorDuplicateKey(Exception):
    pass


def inputs_to_display(
    schema: dict, inputs: str, section: str = "fields"
) -> dict:
    secret_fields = get_secret_fields(schema, section)
    decoded_inputs = inputs_from_store(inputs)
    result = {}

    for key in decoded_inputs.keys():
        if key in secret_fields:
            if decoded_inputs[key]:
                result[key] = ENCRYPTED_STRING
        else:
            result[key] = decoded_inputs[key]

    return result


def get_secret_fields(schema: dict, section: str = "fields") -> list[str]:
    return [
        field["id"]
        for field in schema.get(section, [])
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


def validate_inputs(
    credential_type: "models.CredentialType",
    schema: dict,
    inputs: dict,
    section: str = "fields",
) -> dict:
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
    required_fields = set(schema.get("required", []))

    schema_fields = schema.get("fields", [])
    schema_keys = {field["id"] for field in schema_fields}

    metadata_fields = schema.get("metadata", [])
    metadata_keys = {field["id"] for field in metadata_fields}

    if section == "fields":
        section_keys = schema_keys
        section_fields = schema_fields
        if required_fields:
            required_fields = required_fields - metadata_keys
    else:
        section_keys = metadata_keys
        section_fields = metadata_fields
        if required_fields:
            required_fields = required_fields - schema_keys

    invalid_keys = inputs.keys() - section_keys
    if bool(invalid_keys):
        errors["inputs"] = (
            f"Input keys {invalid_keys} are not defined "
            f"in the schema. Allowed keys are: {section_keys}"
        )

        return errors

    for data in section_fields:
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
            if not isinstance(user_input, str) and not isinstance(
                user_input, bool
            ):
                msg = (
                    f"Input fields must have a boolean or string value. "
                    f"The value provided in the '{field}' field is of "
                    f"type {type(user_input).__name__}."
                )

                errors[display_field] = [msg]
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

        # We apply particular requirements on "host" when it is
        # associated with a container registry.
        if (
            (credential_type.name == enums.DefaultCredentialType.REGISTRY)
            and (field == "host")
            and user_input
        ):
            result = _validate_registry_host_name(user_input)
            if bool(result):
                errors[display_field] = result

        if field == "gpg_public_key":
            result = _validate_gpg_public_key(user_input)
            if bool(result):
                errors[display_field] = result

        # Special validation for mTLS certificate and subject
        if credential_type.name == enums.EventStreamCredentialType.MTLS:
            # Also validate subject format if provided
            if field == "subject" and user_input:
                subject_errors = _validate_certificate_subject_format(
                    user_input
                )
                if bool(subject_errors):
                    errors["inputs.subject"] = subject_errors

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
        return errors

    if not isinstance(fields, list):
        errors.append("'fields' must be a list")
    else:
        id_fields = _get_id_fields(schema)
        metadata_fields = _get_id_fields(schema, "metadata")
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

            default_value = field.get("default")
            if default_value is not None:
                if not isinstance(default_value, (str, bool)):
                    errors.append(
                        f"default for field '{field.get('id')}' "
                        "must be a string or boolean"
                    )

    required_fields = schema.get("required")
    if required_fields:
        if not isinstance(required_fields, list):
            errors.append("required must be a list of strings")
        else:
            for field_id in required_fields:
                if (
                    field_id not in id_fields
                    and field_id not in metadata_fields
                ):
                    errors.append(f"required field {field_id} does not exist")

    return errors


def validate_injectors(schema: dict, injectors: dict) -> dict:
    errors = []

    if not isinstance(injectors, dict):
        errors.append("Injectors must be in Key-Value pairs format")

    injector_keys = set(injectors.keys())
    if not injector_keys.issubset(SUPPORTED_KEYS_IN_INJECTORS):
        errors.append(
            "Injectors must have keys defined in"
            f" {sorted(SUPPORTED_KEYS_IN_INJECTORS)}"
        )

    context = _default_context(schema, injectors)
    key_names = []
    for field in SUPPORTED_KEYS_IN_INJECTORS:
        input_data = injectors.get(field)
        if not input_data:
            continue

        if not isinstance(input_data, dict):
            errors.append(f"{field} must be a dict type")
            continue

        try:
            if field in ["extra_vars", "env"]:
                check_reserved_keys_in_extra_vars(input_data)
        except ValidationError as e:
            errors.append(e.message)
            continue

        for k, v in input_data.items():
            try:
                if k in key_names:
                    raise InjectorDuplicateKey(
                        f"Injector {field} key: {k} already exists"
                    )

                if field == "file":
                    _validate_file_template_key(k, key_names)
                if isinstance(v, str):
                    _check_jinja_string(v, context)
                key_names.append(k)
            except InjectorMissingKeyException as e:
                errors.append(
                    f"Injector key: {k} has a value which refers to an"
                    f" undefined key error: {e}"
                )
            except (InjectorInvalidTemplateKey, InjectorDuplicateKey) as e:
                errors.append(f"{e}")

    return {"injectors": errors} if bool(errors) else {}


def validate_registry_host_name(host: str) -> None:
    errors = _validate_registry_host_name(host)
    if bool(errors):
        raise serializers.ValidationError(f"invalid host name: {host}")


def _validate_registry_host_name(host: str) -> list[str]:
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


def field_exists(schema: dict, name: str, section: str = "fields") -> bool:
    for field in schema.get(section, []):
        if field.get("id") == name:
            return True
    return False


def _get_id_fields(schema: dict, section: str = "fields") -> list[str]:
    fields = schema.get(section, [])

    return [field.get("id") for field in fields if field.get("id")]


def _default_context(schema: dict, injectors: dict) -> dict:
    context = {}

    fields = schema.get("fields", [])

    for field in fields:
        field_type = field.get("type")
        if field_type == "boolean":
            context[field["id"]] = True
        else:
            context[field["id"]] = ""

        default = field.get("default")
        if default:
            context[field["id"]] = default

        choices = field.get("choices")
        if choices:
            if isinstance(choices, list):
                context[field["id"]] = choices[0]

    _add_file_template_keys(context, injectors.get("file", {}))
    return context


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

    elif data_type == "pem_certificate":
        return _validate_pem_certificate(data)

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


def _validate_file_template_key(key: str, key_names: list[str]) -> None:
    keys = key.split(".")
    if keys[0] != "template":
        raise InjectorInvalidTemplateKey(
            _(
                "Injector %(injector_type)s key: %(key)s "
                "should start with template"
            )
            % {"injector_type": "file", "key": key}
        )
    if len(keys) > 2:
        raise InjectorInvalidTemplateKey(
            _(
                "Injector %(injector_type)s key: %(key)s "
                "cannot contain multiple dots"
            )
            % {"injector_type": "file", "key": key}
        )

    if len(keys) == 1:
        for known_key in key_names:
            if known_key.startswith("template"):
                raise InjectorInvalidTemplateKey(
                    _(
                        "Injector %(injector_type)s key: %(key)s "
                        "cannot be mixed with fully qualified keys"
                    )
                    % {"injector_type": "file", "key": key}
                )
    if len(keys) == 2:
        for known_key in key_names:
            if known_key == "template":
                raise InjectorInvalidTemplateKey(
                    _(
                        "Injector %(injector_type)s key: %(key)s "
                        "cannot be mixed with template key"
                    )
                    % {"injector_type": "file", "key": key}
                )


def check_reserved_keys_in_extra_vars(data: dict[str, Any]) -> None:
    for key in data.keys():
        if key in RESERVED_EXTRA_VAR_KEYS:
            raise ValidationError(
                _(
                    "Extra vars key '%(key)s' cannot be one of these "
                    "reserved keys '%(reserved)s'"
                )
                % {
                    "key": key,
                    "reserved": ", ".join(sorted((RESERVED_EXTRA_VAR_KEYS))),
                }
            )


def _validate_pem_certificate(cert_data: str) -> list[str]:
    """Validate PEM certificate format and content.

    Args:
        cert_data: Certificate data in PEM format

    Returns:
        List of error messages, empty if valid
    """
    errors = []

    if not cert_data or not cert_data.strip():
        errors.append("Certificate data cannot be empty")
        return errors

    certs = []
    try:
        # Try to load as single certificate first
        certs = x509.load_pem_x509_certificates(cert_data.encode("utf-8"))
    except (ValueError, UnsupportedAlgorithm) as e:
        errors.append(f"Invalid PEM certificate format: {str(e)}")

    # Validate certificate is not expired
    for cert in certs:
        now = datetime.now(timezone.utc)

        if now > cert.not_valid_after_utc:
            errors.append(
                f"Certificate has expired: {cert.not_valid_after_utc}"
            )

    return errors


def build_copy_post_data(
    eda_credential: "models.EdaCredential", new_cred_name: str
) -> dict:
    """Build a POST payload data from an existing EDA Credential object."""
    post_data = model_to_dict(eda_credential)
    # Remove 'id' field from post data
    post_data.pop("id")
    post_data["name"] = new_cred_name

    # Update foreign key fields
    post_data["organization_id"] = post_data.pop("organization")
    post_data["credential_type_id"] = post_data.pop("credential_type")
    # Decrypt 'inputs' field value for post data
    if (
        eda_credential.credential_type
        and eda_credential.credential_type.inputs
    ):
        inputs = (
            eda_credential.inputs.get_secret_value()
            if isinstance(eda_credential.inputs, SecretValue)
            else eda_credential.inputs
        )
        decoded_inputs = inputs_from_store(inputs)
        post_data["inputs"] = decoded_inputs

    return post_data


def _add_file_template_keys(context: dict, files: dict) -> None:
    for key in files.keys():
        parts = key.split(".")
        # case key == "template"
        if len(parts) == 1:
            if "eda" in context and "filename" in context["eda"]:
                continue
            context["eda"] = {"filename": ""}
            continue

        # else case key == "template.file1"
        if "eda" in context and "filename" in context["eda"]:
            if isinstance(context["eda"]["filename"], str):
                continue
            context["eda"]["filename"][parts[1]] = ""
        else:
            context["eda"] = {"filename": {parts[1]: ""}}


def add_default_values_to_user_inputs(
    schema: dict, inputs: dict, section: str = "fields"
) -> dict:
    for field in schema.get(section, []):
        key = field.get("id")
        field_type = field.get("type", "string")
        default_value = field.get("default")

        if key not in inputs:
            if field_type == "string":
                inputs[key] = default_value or ""
            if field_type == "boolean":
                inputs[key] = default_value or False

    return inputs


def get_resolved_secrets(obj: "models.EdaCredential") -> dict:
    external_secrets = get_external_secrets(obj.id)

    result = yaml.safe_load(obj.inputs.get_secret_value())

    for key, value in external_secrets.items():
        result[key] = value
    return result


# X.509 Subject Matching Functions


def _validate_certificate_subject_format(subject_string: str) -> list[str]:
    """Validate certificate subject format using X.509 standard parsing.

    Args:
        subject_string: Subject DN string (example: "CN=example.com,O=Test")

    Returns:
        List of error messages, empty if valid
    """
    if not subject_string or not subject_string.strip():
        return []  # Empty subject is allowed

    errors = []

    try:
        # Normalize whitespace using shared logic
        normalized_subject = _normalize_x509_dn_whitespace(subject_string)

        # Parse using X.509 standard library
        parsed_name = x509.Name.from_rfc4514_string(normalized_subject)

        # Additional validations using parsed X.509 Name
        errors.extend(_validate_x509_name_constraints(parsed_name))

    except ValueError as e:
        errors.append(f"Invalid X.509 DN format: {str(e) or subject_string}")
    except Exception as e:
        errors.append(f"Failed to parse subject DN: {str(e)}")

    return errors


def _validate_x509_name_constraints(parsed_name: Any) -> list[str]:
    """Validate X.509 Name object constraints.

    Args:
        parsed_name: Parsed X.509 Name object

    Returns:
        List of error messages, empty if valid
    """
    errors = []

    # Check for duplicate attributes (except DC which can be repeated)
    attr_counts = {}
    for attr in parsed_name:
        oid_name = (
            attr.oid._name if hasattr(attr.oid, "_name") else str(attr.oid)
        )

        # Allow multiple DC (Domain Component) attributes
        if attr.oid == NameOID.DOMAIN_COMPONENT:
            continue

        attr_counts[oid_name] = attr_counts.get(oid_name, 0) + 1

    duplicates = [name for name, count in attr_counts.items() if count > 1]
    if duplicates:
        errors.append(f"Duplicate attributes not allowed: {duplicates}")

    # Validate country code length
    for attr in parsed_name:
        if attr.oid == NameOID.COUNTRY_NAME and len(attr.value) != 2:
            errors.append(f"Country code must be 2 characters: '{attr.value}'")

    return errors


def validate_x509_subject_match(expected: str, actual: str) -> bool:
    """Validate that actual X.509 subject matches expected subject pattern.

    Uses X.509 standard-compliant DN parsing for attribute-level matching.
    Supports regex patterns and is order-independent per X.509 standards.

    Args:
        expected: Expected subject pattern (may contain regex patterns)
        actual: Actual subject from certificate

    Returns:
        bool: True if actual matches expected pattern, False otherwise
    """
    if not expected or not actual:
        return False

    # Normalize whitespace in DN strings
    expected = _normalize_x509_dn_whitespace(expected)
    actual = _normalize_x509_dn_whitespace(actual)

    # Parse actual DN into X.509 Name object
    try:
        actual_name = x509.Name.from_rfc4514_string(actual)
    except ValueError as e:
        LOGGER.error(f"Invalid actual DN format: '{actual}': {e}")
        return False

    # Parse expected DN manually to handle regex patterns
    expected_attrs = _parse_dn_with_regex_patterns(expected)
    if not expected_attrs:
        LOGGER.error(f"Failed to parse expected DN: '{expected}'")
        return False

    # Check each expected attribute against actual certificate
    for attr_name, pattern_value in expected_attrs:
        # Convert attribute name to OID
        attr_oid = _get_oid_from_name(attr_name)
        if not attr_oid:
            LOGGER.error(f"Unknown attribute name: '{attr_name}'")
            return False

        actual_attrs = actual_name.get_attributes_for_oid(attr_oid)
        if not actual_attrs:
            LOGGER.error(
                f"Required attribute {attr_name} not found in actual subject"
            )
            return False

        # Check if any actual attribute matches the expected pattern
        if not _match_regex_pattern_against_attrs(pattern_value, actual_attrs):
            return False

    return True


def _normalize_x509_dn_whitespace(dn: str) -> str:
    """Normalize whitespace in DN string components.

    Args:
        dn: Distinguished Name string

    Returns:
        str: DN with normalized whitespace
    """
    if not dn:
        return dn

    # Split by comma and normalize each component
    components = []
    for component in dn.split(","):
        component = component.strip()
        if "=" in component:
            attr, value = component.split("=", 1)
            attr = attr.strip()
            value = value.strip()
            components.append(f"{attr}={value}")
        else:
            components.append(component)

    return ",".join(components)


def _parse_dn_with_regex_patterns(dn: str) -> list[tuple[str, str]]:
    """Parse DN string that may contain regex patterns in attribute values.

    Args:
        dn: Distinguished Name string with potential regex patterns

    Returns:
        List of (attribute_name, pattern_value) tuples
    """
    if not dn:
        return []

    attrs = []
    # Split by comma, but be careful of commas inside quoted values
    components = dn.split(",")

    for component in components:
        component = component.strip()
        if "=" not in component:
            continue

        attr_name, value = component.split("=", 1)
        attr_name = attr_name.strip().upper()
        value = value.strip()

        attrs.append((attr_name, value))

    return attrs


def _get_oid_from_name(attr_name: str) -> Optional[Any]:
    """Convert attribute name to OID.

    Args:
        attr_name: Attribute name (e.g., 'CN', 'O', 'OU')

    Returns:
        OID object or None if unknown
    """
    name_to_oid = {
        "CN": NameOID.COMMON_NAME,
        "COMMONNAME": NameOID.COMMON_NAME,
        "O": NameOID.ORGANIZATION_NAME,
        "ORGANIZATIONNAME": NameOID.ORGANIZATION_NAME,
        "OU": NameOID.ORGANIZATIONAL_UNIT_NAME,
        "ORGANIZATIONALUNITNAME": NameOID.ORGANIZATIONAL_UNIT_NAME,
        "C": NameOID.COUNTRY_NAME,
        "COUNTRYNAME": NameOID.COUNTRY_NAME,
        "L": NameOID.LOCALITY_NAME,
        "LOCALITYNAME": NameOID.LOCALITY_NAME,
        "ST": NameOID.STATE_OR_PROVINCE_NAME,
        "STATEORPROVINCENAME": NameOID.STATE_OR_PROVINCE_NAME,
        "STREET": NameOID.STREET_ADDRESS,
        "STREETADDRESS": NameOID.STREET_ADDRESS,
        "DC": NameOID.DOMAIN_COMPONENT,
        "DOMAINCOMPONENT": NameOID.DOMAIN_COMPONENT,
        "EMAIL": NameOID.EMAIL_ADDRESS,
        "EMAILADDRESS": NameOID.EMAIL_ADDRESS,
    }

    return name_to_oid.get(attr_name.upper())


def _match_regex_pattern_against_attrs(
    pattern: str, actual_attrs: list[Any]
) -> bool:
    """Match regex pattern against list of actual attributes.

    Args:
        pattern: Regex pattern string
        actual_attrs: List of actual X.509 attributes

    Returns:
        bool: True if pattern matches any actual attribute
    """
    try:
        regex_pattern = f"^{pattern}$"
        return any(
            re.match(regex_pattern, attr.value, re.IGNORECASE)
            for attr in actual_attrs
        )
    except re.error as e:
        LOGGER.error(f"Invalid regex pattern '{pattern}': {e}")
        return False
