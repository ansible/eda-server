#  Copyright 2023 Red Hat, Inc.
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
import hashlib
import logging
import re
import typing as tp
import urllib

import yaml
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from aap_eda.core import enums, models
from aap_eda.core.utils.credentials import (
    check_reserved_keys_in_extra_vars,
    validate_registry_host_name,
    validate_schema,
)
from aap_eda.core.utils.k8s_service_name import is_rfc_1035_compliant

logger = logging.getLogger(__name__)

NOT_ACCEPTABLE_TYPES_FOR_ACTIVATION = [
    enums.DefaultCredentialType.REGISTRY,
    enums.DefaultCredentialType.GPG,
    enums.DefaultCredentialType.SOURCE_CONTROL,
]


def check_if_rulebook_exists(rulebook_id: int) -> int:
    try:
        models.Rulebook.objects.get(pk=rulebook_id)
    except models.Rulebook.DoesNotExist:
        raise serializers.ValidationError(
            f"Rulebook with id {rulebook_id} does not exist"
        )
    return rulebook_id


def check_if_de_exists(decision_environment_id: int) -> int:
    if models.DecisionEnvironment.objects.filter(
        id=decision_environment_id
    ).exists():
        return decision_environment_id
    raise serializers.ValidationError(
        f"DecisionEnvironment with id {decision_environment_id} "
        "does not exist"
    )


def check_if_de_valid(
    image_url: str,
    eda_credential_id: tp.Optional[int] = None,
):
    # The OCI standard format for the image url is a combination of a host
    # (with optional port) separated from the image path (with optional tag) by
    # a slash: <host>[:port]/<path>[:tag].
    #
    # https://github.com/opencontainers/distribution-spec/blob/8376368dd8aadc33bf6c88a8b765df90287bb5c8/spec.md?plain=1#L155 # noqa: E501
    #
    # We split the image url on the first slash into the host and path.  The
    # path is further split into a name and tag on the rightmost colon.
    #
    # The path and tag are validated using the OCI regexes for each.
    split = image_url.split("/", 1)
    host = split[0]
    path = split[1] if len(split) > 1 else None

    if host == "":
        message = _(
            "Image url %(image_url)s is malformed; no host name found"
        ) % {"image_url": image_url}
        raise serializers.ValidationError({"image_url": message})

    try:
        validate_registry_host_name(host)
    except serializers.ValidationError:
        # We raise our own instance of this exception in order to assert
        # control over the format of the message.
        message = _(
            "Image url %(image_url)s is malformed; "
            "invalid host name: '%(host)s'"
        ) % {"image_url": image_url, "host": host}
        raise serializers.ValidationError({"image_url": message})

    if (path is None) or (path == ""):
        message = _(
            "Image url %(image_url)s is malformed; no image path found"
        ) % {"image_url": image_url}
        raise serializers.ValidationError({"image_url": message})

    digest = False
    if "@sha256" in path or "@sha512" in path:
        split = path.split("@", 1)
        name = split[0]
        digest = True
    else:
        split = path.split(":", 1)
        name = split[0]
    # Get the tag sans any additional content.  Any additional content
    # is passed without validation.
    tag = split[1] if (len(split) > 1) else None
    tag = tag if tag is None else tag.split("@", 1)[0]

    if not re.fullmatch(
        r"[[a-z0-9]+((\.|_|__|-+)[a-z0-9]+)*(\/[a-z0-9]+((\.|_|__|-+)[a-z0-9]+)*)*",  # noqa: E501
        name,
    ):
        message = _(
            "Image url %(image_url)s is malformed; "
            "'%(name)s' does not match OCI name standard"
        ) % {"image_url": image_url, "name": name}
        raise serializers.ValidationError({"image_url": message})

    if (not digest and tag is not None) and (
        not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9._-]{0,127}", tag)
    ):
        message = _(
            "Image url %(image_url)s is malformed; "
            "'%(tag)s' does not match OCI tag standard"
        ) % {"image_url": image_url, "tag": tag}
        raise serializers.ValidationError({"image_url": message})

    if eda_credential_id:
        credential = get_credential_if_exists(eda_credential_id)
        inputs = yaml.safe_load(credential.inputs.get_secret_value())
        credential_host = inputs.get("host")

        if not credential_host:
            message = _(
                "Credential %(name)s needs to have host information"
            ) % {"name": credential.name}
            raise serializers.ValidationError({"image_url": message})

        # Check that the host matches the credential host.
        # For backward compatibility when creating a new DE with
        # an old credential we need to separate any
        # scheme from the host before doing the compare.
        parsed_credential_host = urllib.parse.urlparse(credential_host)
        # If there's a netloc that's the host to use; if not, it's the path if
        # there is no scheme else it's the scheme and path joined by a colon.
        if parsed_credential_host.netloc:
            parsed_host = parsed_credential_host.netloc
        else:
            parsed_host = parsed_credential_host.path
            if parsed_credential_host.scheme:
                parsed_host = ":".join(
                    [parsed_credential_host.scheme, parsed_host]
                )

        if host != parsed_host:
            message = _(
                "DecisionEnvironment image url: %(image_url)s does "
                "not match with the credential host: %(host)s"
            ) % {"image_url": image_url, "host": credential_host}
            raise serializers.ValidationError({"image_url": message})


def get_credential_if_exists(eda_credential_id: int) -> models.EdaCredential:
    try:
        return models.EdaCredential.objects.get(pk=eda_credential_id)
    except models.EdaCredential.DoesNotExist:
        raise serializers.ValidationError(
            f"EdaCredential with id {eda_credential_id} does not exist"
        )


def check_credential_types_for_activation(eda_credential_id: int) -> int:
    check_credential_types(
        eda_credential_id,
        types=NOT_ACCEPTABLE_TYPES_FOR_ACTIVATION,
        negative=True,
    )

    return eda_credential_id


def check_credential_types_for_gpg(eda_credential_id: int) -> int:
    check_credential_types(
        eda_credential_id, [enums.DefaultCredentialType.GPG]
    )

    return eda_credential_id


def check_credential_types_for_scm(eda_credential_id: int) -> int:
    check_credential_types(
        eda_credential_id,
        [enums.DefaultCredentialType.SOURCE_CONTROL],
    )

    return eda_credential_id


def check_multiple_credentials(
    eda_credential_ids: list[int],
) -> list[int]:
    for eda_credential_id in eda_credential_ids:
        check_credential_types_for_activation(eda_credential_id)

    return eda_credential_ids


def check_single_aap_credential(
    eda_credential_ids: list[int],
) -> list[int]:
    credentials = [
        get_credential_if_exists(eda_credential_id)
        for eda_credential_id in eda_credential_ids
    ]
    aap_credential_ids = [
        credential.id
        for credential in credentials
        if credential.credential_type.name == enums.DefaultCredentialType.AAP
    ]

    if len(aap_credential_ids) > 1:
        raise serializers.ValidationError(
            _("%(number)d RH AAP credentials are provided instead of 1")
            % {"number": len(aap_credential_ids)}
        )

    return eda_credential_ids


def check_if_credential_type_exists(credential_type_id: int) -> int:
    try:
        models.CredentialType.objects.get(pk=credential_type_id)
    except models.CredentialType.DoesNotExist:
        raise serializers.ValidationError(
            f"CredentialType with id {credential_type_id} does not exist"
        )
    return credential_type_id


def check_if_credential_name_used(name: str) -> str:
    if not name:
        raise serializers.ValidationError("Name parameter is missing.")
    if models.EdaCredential.objects.filter(name=name).exists():
        raise serializers.ValidationError(
            f"Credential name already exists: {name}"
        )
    return name


def check_if_organization_exists(organization_id: int) -> int:
    try:
        models.Organization.objects.get(pk=organization_id)
    except models.Organization.DoesNotExist:
        raise serializers.ValidationError(
            f"Organization with id {organization_id} does not exist"
        )
    return organization_id


def check_if_extra_var_exists(extra_var_id: int) -> int:
    try:
        models.ExtraVar.objects.get(pk=extra_var_id)
    except models.ExtraVar.DoesNotExist:
        raise serializers.ValidationError(
            f"ExtraVar with id {extra_var_id} does not exist"
        )
    return extra_var_id


def check_if_awx_token_exists(awx_token_id: int) -> int:
    try:
        models.AwxToken.objects.get(pk=awx_token_id)
    except models.AwxToken.DoesNotExist:
        raise serializers.ValidationError(
            f"AwxToken with id {awx_token_id} does not exist"
        )
    return awx_token_id


def check_rulesets_require_token(
    rulesets_data: list[dict[str, tp.Any]],
) -> bool:
    """Inspect rulesets data to determine if a token is required.

    Return True if any of the rules has an action that requires a token.
    """
    required_actions = {"run_job_template", "run_workflow_template"}

    for ruleset in rulesets_data:
        for rule in ruleset.get("rules", []):
            # When it is a single action dict
            if any(
                action_key in required_actions
                for action_key in rule.get("action", {})
            ):
                return True

            # When it is a list of actions
            if any(
                action_arg in required_actions
                for action in rule.get("actions", [])
                for action_arg in action
            ):
                return True

    return False


def is_extra_var_dict(extra_var: str):
    try:
        data = yaml.safe_load(extra_var)
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                "Extra var is not in object format"
            )
        check_reserved_keys_in_extra_vars(data)
    except yaml.YAMLError:
        raise serializers.ValidationError(
            "Extra var must be in JSON or YAML format"
        )


def check_if_schema_valid(schema: dict):
    errors = validate_schema(schema)

    if bool(errors):
        raise serializers.ValidationError(errors)


def check_if_rfc_1035_compliant(service_name: str):
    if settings.DEPLOYMENT_TYPE == "k8s" and not is_rfc_1035_compliant(
        service_name
    ):
        raise serializers.ValidationError(
            f"{service_name} must be a valid RFC 1035 label name"
        )


def check_credential_types(
    eda_credential_id: int,
    types: list[enums.DefaultCredentialType],
    negative: bool = False,
) -> None:
    credential = get_credential_if_exists(eda_credential_id)
    name = credential.credential_type.name

    names = [ctype.value for ctype in types]
    if negative and name in names:
        raise serializers.ValidationError(
            f"The type of credential can not be one of {names}"
        )
    if not negative and name not in names:
        raise serializers.ValidationError(
            f"The type of credential can only be one of {names}"
        )


def check_credential_registry_username_password(
    eda_credential_id: int,
) -> int:
    credential = get_credential_if_exists(eda_credential_id)
    name = credential.credential_type.name
    if name != enums.DefaultCredentialType.REGISTRY.value:
        raise serializers.ValidationError(
            "The type of credential can only be one of "
            f"['{enums.DefaultCredentialType.REGISTRY}']"
        )
    inputs = yaml.safe_load(credential.inputs.get_secret_value())
    password = inputs.get("password", "")
    if not password:
        raise serializers.ValidationError(
            "Need username and password or just token in credential"
        )
    return eda_credential_id


def valid_hash_algorithm(algo: str):
    """Check hash algorithm."""
    if algo not in hashlib.algorithms_available:
        raise serializers.ValidationError(
            (
                f"Invalid hash algorithm {algo} should "
                f"be one of {hashlib.algorithms_available}"
            )
        )


def valid_hash_format(fmt: str):
    """Check hash format type."""
    if fmt not in enums.SignatureEncodingType.values():
        raise serializers.ValidationError(
            (
                f"Invalid hash format {fmt} should "
                f"be one of {enums.SignatureEncodingType.values()}"
            )
        )
    return fmt


def _validate_event_stream_settings(auth_type: str):
    """Check event stream settings."""
    if (
        auth_type == enums.EventStreamCredentialType.MTLS
        and not settings.EVENT_STREAM_MTLS_BASE_URL
    ):
        raise serializers.ValidationError(
            (
                f"EventStream of type {auth_type} cannot be used "
                "because EVENT_STREAM_MTLS_BASE_URL is not configured. "
                "Please check with your site administrator."
            )
        )

    if (
        auth_type != enums.EventStreamCredentialType.MTLS
        and not settings.EVENT_STREAM_BASE_URL
    ):
        raise serializers.ValidationError(
            (
                f"EventStream of type {auth_type} cannot be used "
                "because EVENT_STREAM_BASE_URL is not configured. "
                "Please check with your site administrator."
            )
        )


def check_if_event_streams_exists(event_stream_ids: list[int]) -> list[int]:
    """Check a event stream exists."""
    for event_stream_id in event_stream_ids:
        try:
            models.EventStream.objects.get(pk=event_stream_id)
        except models.EventStream.DoesNotExist as exc:
            raise serializers.ValidationError(
                f"EventStream with id {event_stream_id} does not exist"
            ) from exc
    return event_stream_ids


def check_credential_types_for_event_stream(eda_credential_id: int) -> int:
    """Check the credential types for a event stream."""
    credential = get_credential_if_exists(eda_credential_id)
    name = credential.credential_type.name
    names = (
        enums.EventStreamCredentialType.values()
        + enums.CustomEventStreamCredentialType.values()
    )
    if name not in names:
        raise serializers.ValidationError(
            f"The type of credential can only be one of {names}"
        )

    _validate_event_stream_settings(name)
    return eda_credential_id


def check_if_activation_name_used(name: str) -> str:
    if models.Activation.objects.filter(name=name).first():
        raise serializers.ValidationError(
            f"Activation with name {name} already exists"
        )
    return name
