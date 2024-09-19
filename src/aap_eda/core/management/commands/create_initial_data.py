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
from urllib.parse import urlparse

from ansible_base.rbac import permission_registry
from ansible_base.rbac.models import DABPermission, RoleDefinition
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q

from aap_eda.conf import settings_registry
from aap_eda.core import enums, models
from aap_eda.core.tasking import enable_redis_prefix
from aap_eda.core.utils.credentials import inputs_to_store

NEW_HELP_TEXT = (
    "Red Hat Ansible Automation Platform base URL to authenticate with.",
    "For Event-Driven Ansible controller 2.5 with Ansible Automation Controller 2.4, use the following example: https://<<your_controller_host>>",  # noqa E501
    "For Ansible Automation Controller 2.5, use the following example: https://<<your_gateway_host>>/api/controller/",  # noqa E501
)

ORIG_HELP_TEXT = (
    "Red Hat Ansible Automation Platform base URL to authenticate with."
)

CRUD = ["add", "view", "change", "delete"]
LOGGER = logging.getLogger(__name__)
AVAILABLE_ALGORITHMS = sorted(hashlib.algorithms_available)
AUTH_TYPE_LABEL = "Event Stream Authentication Type"
SIGNATURE_ENCODING_LABEL = "Signature Encoding"
HTTP_HEADER_LABEL = "HTTP Header Key"
DEPRECATED_CREDENTIAL_KINDS = ["mtls"]
# FIXME(cutwater): Role descriptions were taken from the RBAC design document
#  and must be updated.
ORG_ROLES = [
    {
        "name": "Organization Admin",
        "description": (
            "Has all permissions to a single organization and all objects "
            "inside of it"
        ),
        "permissions": {
            "activation": [
                "add",
                "view",
                "delete",
                "enable",
                "disable",
                "restart",
            ],
            "rulebook_process": ["view"],
            "audit_rule": ["view"],
            "organization": ["view", "change", "delete"],
            "team": CRUD + ["member"],
            "project": CRUD + ["sync"],
            "rulebook": ["view"],
            "decision_environment": CRUD,
            "eda_credential": CRUD,
            "event_stream": CRUD,
        },
    },
    {
        "name": "Organization Member",
        "description": "Users who are a part of the organization",
        "permissions": {
            "organization": ["view", "member"],
        },
    },
    {
        "name": "Organization Editor",
        "description": (
            "Has create and update permissions to all objects within "
            "a single organization"
        ),
        "permissions": {
            "activation": ["add", "view"],
            "rulebook_process": ["view"],
            "audit_rule": ["view"],
            "organization": ["view"],
            "team": ["view"],
            "project": ["add", "view", "change"],
            "rulebook": ["view"],
            "decision_environment": ["add", "view", "change"],
            "eda_credential": ["add", "view", "change"],
            "event_stream": ["add", "view", "change"],
        },
    },
    {
        "name": "Organization Contributor",
        "description": (
            "Has create and update permissions to all objects and "
            "enable/disable/restart permissions to all rulebook activations "
            "within a single organization"
        ),
        "permissions": {
            "activation": [
                "add",
                "view",
                "enable",
                "disable",
                "restart",
            ],
            "rulebook_process": ["view"],
            "audit_rule": ["view"],
            "organization": ["view"],
            "team": ["view"],
            "project": ["add", "view", "change"],
            "rulebook": ["view"],
            "decision_environment": ["add", "view", "change"],
            "eda_credential": ["add", "view", "change"],
            "event_stream": ["add", "view", "change"],
        },
    },
    {
        "name": "Organization Operator",
        "description": (
            "Has read permission to all objects and enable/disable/restart "
            "permissions for all rulebook activations within a single "
            "organization"
        ),
        "permissions": {
            "activation": ["view", "enable", "disable", "restart"],
            "rulebook_process": ["view"],
            "audit_rule": ["view"],
            "organization": ["view"],
            "team": ["view"],
            "project": ["view"],
            "rulebook": ["view"],
            "decision_environment": ["view"],
            "eda_credential": ["view"],
            "event_stream": ["view"],
        },
    },
    {
        "name": "Organization Auditor",
        "description": (
            "Has read permission to all objects within a single organization"
        ),
        "permissions": {
            "activation": ["view"],
            "rulebook_process": ["view"],
            "audit_rule": ["view"],
            "organization": ["view"],
            "team": ["view"],
            "project": ["view"],
            "rulebook": ["view"],
            "decision_environment": ["view"],
            "eda_credential": ["view"],
            "event_stream": ["view"],
        },
    },
    {
        "name": "Organization Viewer",
        "description": (
            "Has read permission to all objects within a single organization"
        ),
        "permissions": {
            "activation": ["view"],
            "rulebook_process": ["view"],
            "audit_rule": ["view"],
            "organization": ["view"],
            "team": ["view"],
            "project": ["view"],
            "rulebook": ["view"],
            "decision_environment": ["view"],
            "eda_credential": ["view"],
            "event_stream": ["view"],
        },
    },
]

SOURCE_CONTROL_INPUTS = {
    "fields": [
        {"id": "username", "label": "Username", "type": "string"},
        {
            "id": "password",
            "label": "Password",
            "type": "string",
            "secret": True,
        },
        {
            "id": "ssh_key_data",
            "label": "SCM Private Key",
            "type": "string",
            "format": "ssh_private_key",
            "secret": True,
            "multiline": True,
        },
        {
            "id": "ssh_key_unlock",
            "label": "Private Key Passphrase",
            "type": "string",
            "secret": True,
        },
    ]
}

REGISTRY_INPUTS = {
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

GPG_INPUTS = {
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
    ],
    "required": ["gpg_public_key"],
}

AAP_INPUTS = {
    "fields": [
        {
            "id": "host",
            "label": "Red Hat Ansible Automation Platform",
            "type": "string",
            "help_text": NEW_HELP_TEXT,
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
        },
    ],
    "required": ["host"],
}

AAP_INJECTORS = {
    "env": {
        "TOWER_HOST": "{{host}}",
        "TOWER_USERNAME": "{{username}}",
        "TOWER_PASSWORD": "{{password}}",
        "TOWER_VERIFY_SSL": "{{verify_ssl}}",
        "TOWER_OAUTH_TOKEN": "{{oauth_token}}",
        "CONTROLLER_HOST": "{{host}}",
        "CONTROLLER_USERNAME": "{{username}}",
        "CONTROLLER_PASSWORD": "{{password}}",
        "CONTROLLER_VERIFY_SSL": "{{verify_ssl}}",
        "CONTROLLER_OAUTH_TOKEN": "{{oauth_token}}",
    }
}

VAULT_INPUTS = {
    "fields": [
        {
            "id": "vault_password",
            "label": "Vault Password",
            "type": "string",
            "secret": True,
            "ask_at_runtime": True,
        },
        {
            "id": "vault_id",
            "label": "Vault Identifier",
            "type": "string",
            "format": "vault_id",
            "help_text": (
                "Specify an (optional) Vault ID. This is equivalent "
                "to specifying the --vault-id Ansible parameter for "
                "providing multiple Vault passwords.  Note: this "
                " feature only works in Ansible 2.4+."
            ),
        },
    ],
    "required": ["vault_password"],
}

EVENT_STREAM_HMAC_INPUTS = {
    "fields": [
        {
            "id": "auth_type",
            "label": AUTH_TYPE_LABEL,
            "type": "string",
            "default": "hmac",
            "hidden": True,
        },
        {
            "id": "secret",
            "label": "Secret",
            "type": "string",
            "secret": True,
            "help_text": (
                "The symmetrical shared secret between EDA and the "
                "Event Stream Server. Please save this value since "
                "you would need it on the Event Stream Server."
            ),
        },
        {
            "id": "hash_algorithm",
            "label": "Hash algorithm",
            "type": "string",
            "default": "sha256",
            "choices": AVAILABLE_ALGORITHMS,
            "help_text": (
                "The EventStream sender hashes the message being "
                "sent using one of these algorithms, which guarantees "
                "message integrity."
            ),
        },
        {
            "id": "http_header_key",
            "label": "HMAC Header Key",
            "type": "string",
            "default": "X-Hub-Signature-256",
            "help_text": (
                "The event stream sender typically uses a special HTTP header "
                "to send the signature of the payload. e.g X-Hub-Signature-256"
            ),
        },
        {
            "id": "signature_encoding",
            "label": SIGNATURE_ENCODING_LABEL,
            "type": "string",
            "default": "base64",
            "choices": ["base64", "hex"],
            "help_text": (
                "The payload signature which is binary is converted as a "
                "base64 or hex strings before being added to the HTTP header"
            ),
        },
        {
            "id": "signature_prefix",
            "label": "Signature prefix",
            "type": "string",
            "help_text": (
                "The signature might optionally have a prefix.e.g sha256="
            ),
        },
    ],
    "required": [
        "auth_type",
        "secret",
        "hash_algorithm",
        "http_header_key",
        "signature_encoding",
    ],
}

EVENT_STREAM_BASIC_INPUTS = {
    "fields": [
        {
            "id": "auth_type",
            "label": AUTH_TYPE_LABEL,
            "type": "string",
            "default": "basic",
            "hidden": True,
        },
        {
            "id": "username",
            "label": "Username",
            "type": "string",
            "help_text": (
                "The username used to authenticate the incoming event stream"
            ),
        },
        {
            "id": "password",
            "label": "Password",
            "type": "string",
            "secret": True,
            "help_text": (
                "The password used to authenticate the incoming event stream"
            ),
        },
        {
            "id": "http_header_key",
            "label": HTTP_HEADER_LABEL,
            "type": "string",
            "default": "Authorization",
            "hidden": True,
        },
    ],
    "required": ["auth_type", "password", "username", "http_header_key"],
}

EVENT_STREAM_TOKEN_INPUTS = {
    "fields": [
        {
            "id": "auth_type",
            "label": AUTH_TYPE_LABEL,
            "type": "string",
            "default": "token",
            "hidden": True,
        },
        {
            "id": "token",
            "label": "Token",
            "type": "string",
            "secret": True,
            "help_text": (
                "The symmetrical shared token between EDA and the EventStream "
                "Server. Please save this value since you would need it on "
                "the EventStream Server."
            ),
        },
        {
            "id": "http_header_key",
            "label": HTTP_HEADER_LABEL,
            "type": "string",
            "default": "Authorization",
            "help_text": (
                "The HTTP header for passing in the token usually this is "
                "Authorization but some sites use a different header, "
                "e.g. X-Gitlab-Token"
            ),
        },
    ],
    "required": ["auth_type", "token", "http_header_key"],
}

EVENT_STREAM_OAUTH2_INPUTS = {
    "fields": [
        {
            "id": "auth_type",
            "label": AUTH_TYPE_LABEL,
            "type": "string",
            "default": "oauth2",
            "hidden": True,
        },
        {
            "id": "client_id",
            "label": "Client ID",
            "type": "string",
            "help_text": ("The Client ID from the Authorization Server."),
        },
        {
            "id": "client_secret",
            "label": "Client Secret",
            "type": "string",
            "secret": True,
            "help_text": ("The Client Secret from the Authorization Server."),
        },
        {
            "id": "introspection_url",
            "label": "Introspection URL",
            "type": "string",
            "help_text": (
                "The Introspection URL from the Authorization Server "
                "as defined in RFC 7662."
            ),
        },
        {
            "id": "http_header_key",
            "label": HTTP_HEADER_LABEL,
            "type": "string",
            "default": "Authorization",
            "hidden": True,
            "help_text": (
                "The HTTP header for passing in the token usually this is "
                "Authorization."
            ),
        },
    ],
    "required": [
        "auth_type",
        "http_header_key",
        "client_secret",
        "client_id",
        "introspection_url",
    ],
}

EVENT_STREAM_OAUTH2_JWT_INPUTS = {
    "fields": [
        {
            "id": "auth_type",
            "label": AUTH_TYPE_LABEL,
            "type": "string",
            "default": "oauth2-jwt",
            "hidden": True,
        },
        {
            "id": "jwks_url",
            "label": "JWKS URL",
            "type": "string",
            "help_text": (
                "JSON Web Key Sets URL to fetch public keys to validate "
                "JWT token. Its usually "
                "https://<your auth server>/.well-known/jwks.json"
            ),
        },
        {
            "id": "audience",
            "label": "Audience",
            "type": "string",
            "help_text": (
                "Audience from the JWT claims, if specified we will "
                "validate the audience in the JWT claims."
            ),
        },
        {
            "id": "http_header_key",
            "label": HTTP_HEADER_LABEL,
            "type": "string",
            "default": "Authorization",
            "hidden": True,
            "help_text": (
                "The HTTP header for passing in the token usually this is "
                "Authorization."
            ),
        },
    ],
    "required": ["auth_type", "jwks_url", "http_header_key"],
}

EVENT_STREAM_ECDSA_INPUTS = {
    "fields": [
        {
            "id": "auth_type",
            "label": AUTH_TYPE_LABEL,
            "type": "string",
            "default": "ecdsa",
            "hidden": True,
        },
        {
            "id": "http_header_key",
            "label": "Primary Header Key",
            "type": "string",
            "help_text": (
                "The sender will use this HTTP header to pass in "
                "the signature"
            ),
        },
        {
            "id": "public_key",
            "label": "Public Key",
            "type": "string",
            "help_text": (
                "Public Key for validating the data, this would be "
                "available from the sender after you have created the "
                "event stream on their side with our URL. This is usually a "
                "2 step process"
            ),
            "multiline": True,
        },
        {
            "id": "prefix_http_header_key",
            "label": "Additional Prefix Header Key",
            "type": "string",
            "help_text": "Additional Header Key for ECDSA.",
        },
        {
            "id": "signature_encoding",
            "label": SIGNATURE_ENCODING_LABEL,
            "type": "string",
            "default": "base64",
            "choices": ["base64", "hex"],
            "help_text": (
                "The payload signature which is binary is converted "
                "as a base64 or hex strings before being added to "
                "the HTTP header"
            ),
        },
        {
            "id": "hash_algorithm",
            "label": "Hash algorithm",
            "type": "string",
            "default": "sha256",
            "choices": AVAILABLE_ALGORITHMS,
            "help_text": (
                "The EventStream sender hashes the message being "
                "sent using one of these algorithms, which guarantees "
                "message integrity."
            ),
        },
    ],
    "required": [
        "auth_type",
        "http_header_key",
        "public_key",
        "signature_encoding",
        "hash_algorithm",
    ],
}


EVENT_STREAM_GITLAB_INPUTS = {
    "fields": [
        {
            "id": "auth_type",
            "label": AUTH_TYPE_LABEL,
            "type": "string",
            "default": "token",
            "hidden": True,
        },
        {
            "id": "token",
            "label": "Token",
            "type": "string",
            "secret": True,
            "help_text": (
                "The symmetrical shared token between EDA and the Gitlab "
                "Server. Please save this value since you would need it on "
                "the EventStream Server."
            ),
        },
        {
            "id": "http_header_key",
            "label": HTTP_HEADER_LABEL,
            "type": "string",
            "default": "X-Gitlab-Token",
            "help_text": (
                "The HTTP header for passing in the token usually "
                "this is Authorization but some sites use a different "
                "header, e.g. X-Gitlab-Token"
            ),
            "hidden": True,
        },
    ],
    "required": ["auth_type", "token", "http_header_key"],
}

EVENT_STREAM_GITHUB_INPUTS = {
    "fields": [
        {
            "id": "auth_type",
            "label": AUTH_TYPE_LABEL,
            "type": "string",
            "default": "hmac",
            "hidden": True,
        },
        {
            "id": "secret",
            "label": "HMAC Secret",
            "type": "string",
            "secret": True,
            "help_text": (
                "The symmetrical shared secret between EDA and "
                "the EventStream Server. Please save this value since "
                "you would need it on the EventStream Server."
            ),
        },
        {
            "id": "hash_algorithm",
            "label": "HMAC Algorithm",
            "type": "string",
            "default": "sha256",
            "choices": ["sha128", "sha256", "sha512", "sha1024"],
            "help_text": (
                "The EventStream sender hashes the message being sent "
                "using one of these algorithms, which guarantees "
                "message integrity."
            ),
            "hidden": True,
        },
        {
            "id": "http_header_key",
            "label": HTTP_HEADER_LABEL,
            "type": "string",
            "default": "X-Hub-Signature-256",
            "help_text": (
                "The event stream sender typically uses a special "
                "HTTP header to send the signature of the payload. "
                "e.g X-Hub-Signature-256"
            ),
            "hidden": True,
        },
        {
            "id": "signature_encoding",
            "label": SIGNATURE_ENCODING_LABEL,
            "type": "string",
            "default": "hex",
            "choices": ["base64", "hex"],
            "help_text": (
                "The payload signature which is binary is converted "
                "as a base64 or hex strings before being added to "
                "the HTTP header"
            ),
            "hidden": True,
        },
        {
            "id": "signature_prefix",
            "label": "Signature prefix",
            "type": "string",
            "default": "sha256=",
            "help_text": (
                "The signature might optionally have a prefix.e.g sha256="
            ),
            "hidden": True,
        },
    ],
    "required": [
        "auth_type",
        "secret",
        "hash_algorithm",
        "http_header_key",
        "signature_encoding",
        "signature_prefix",
    ],
}

EVENT_STREAM_SNOW_INPUTS = {
    "fields": [
        {
            "id": "auth_type",
            "label": AUTH_TYPE_LABEL,
            "type": "string",
            "default": "token",
            "hidden": True,
        },
        {
            "id": "token",
            "label": "Token",
            "type": "string",
            "secret": True,
            "help_text": (
                "The symmetrical shared token between EDA and the ServiceNow "
                "Server. Please save this value since you would need it on "
                "the EventStream Server."
            ),
        },
        {
            "id": "http_header_key",
            "label": HTTP_HEADER_LABEL,
            "type": "string",
            "default": "Authorization",
            "help_text": (
                "The HTTP header for passing in the token usually this "
                "is Authorization but some sites use a different header, "
                "e.g. X-Gitlab-Token"
            ),
            "hidden": True,
        },
    ],
    "required": ["auth_type", "token", "http_header_key"],
}

EVENT_STREAM_DYNATRACE_INPUTS = {
    "fields": [
        {
            "id": "auth_type",
            "label": AUTH_TYPE_LABEL,
            "type": "string",
            "default": "basic",
            "hidden": True,
        },
        {
            "id": "username",
            "label": "Username",
            "type": "string",
            "help_text": (
                "The username used to authenticate the incoming event stream"
            ),
        },
        {
            "id": "password",
            "label": "Password",
            "type": "string",
            "secret": True,
            "help_text": (
                "The password used to authenticate the incoming event stream"
            ),
        },
        {
            "id": "http_header_key",
            "label": HTTP_HEADER_LABEL,
            "type": "string",
            "default": "Authorization",
            "help_text": (
                "The HTTP header for passing in the credentials usually "
                "this is Authorization."
            ),
            "hidden": True,
        },
    ],
    "required": ["auth_type", "username", "password", "http_header_key"],
}

CREDENTIAL_TYPES = [
    {
        "name": enums.DefaultCredentialType.SOURCE_CONTROL,
        "namespace": "scm",
        "kind": "scm",
        "inputs": SOURCE_CONTROL_INPUTS,
        "injectors": {},
        "managed": True,
    },
    {
        "name": enums.DefaultCredentialType.REGISTRY,
        "kind": "registry",
        "namespace": "registry",
        "inputs": REGISTRY_INPUTS,
        "injectors": {},
        "managed": True,
    },
    {
        "name": enums.DefaultCredentialType.GPG,
        "kind": "cryptography",
        "namespace": "gpg_public_key",
        "inputs": GPG_INPUTS,
        "injectors": {},
        "managed": True,
    },
    {
        "name": enums.DefaultCredentialType.AAP,
        "kind": "cloud",
        "namespace": "controller",
        "inputs": AAP_INPUTS,
        "injectors": AAP_INJECTORS,
        "managed": True,
    },
    {
        "name": enums.DefaultCredentialType.VAULT,
        "namespace": "vault",
        "kind": "vault",
        "inputs": VAULT_INPUTS,
        "injectors": {},
        "managed": True,
    },
    {
        "name": enums.EventStreamCredentialType.HMAC,
        "namespace": "event_stream",
        "kind": "hmac",
        "inputs": EVENT_STREAM_HMAC_INPUTS,
        "injectors": {},
        "managed": True,
        "description": (
            "Credential for Event Streams that use HMAC. "
            "This requires shared secret between the sender and receiver. "
            "The signature can be sent as hex or base64 strings. "
            "Most of senders will use a special HTTP header to send "
            "the signature data."
        ),
    },
    {
        "name": enums.EventStreamCredentialType.BASIC,
        "namespace": "event_stream",
        "kind": "basic",
        "inputs": EVENT_STREAM_BASIC_INPUTS,
        "injectors": {},
        "managed": True,
        "description": (
            "Credential for EventStreams that use Basic Authentication. "
            "It requires a username and password"
        ),
    },
    {
        "name": enums.EventStreamCredentialType.TOKEN,
        "namespace": "event_stream",
        "kind": "token",
        "inputs": EVENT_STREAM_TOKEN_INPUTS,
        "injectors": {},
        "managed": True,
        "description": (
            "Credential for Event Streams that use Token Authentication. "
            "Usually the token is sent in the Authorization header. "
            "Some of the senders will use a special HTTP header to send "
            "the token."
        ),
    },
    {
        "name": enums.EventStreamCredentialType.OAUTH2,
        "namespace": "event_stream",
        "kind": "oauth2",
        "inputs": EVENT_STREAM_OAUTH2_INPUTS,
        "injectors": {},
        "managed": True,
        "description": (
            "Credential for Event Streams that use OAuth2. "
            "This needs a client id and client credential and access "
            "to an Authorization server so we can introspect the token "
            "being sent."
        ),
    },
    {
        "name": enums.EventStreamCredentialType.OAUTH2_JWT,
        "namespace": "event_stream",
        "kind": "oauth2_jwt",
        "inputs": EVENT_STREAM_OAUTH2_JWT_INPUTS,
        "injectors": {},
        "managed": True,
        "description": (
            "Credential for Event Streams that use OAuth2 with JWT. "
            "This needs a JWKS URL which will be used to fetch the "
            "public key and validate the incoming token. If an audience "
            "is specified we will check the audience in the JWT claims."
        ),
    },
    {
        "name": enums.EventStreamCredentialType.ECDSA,
        "namespace": "event_stream",
        "kind": "ecdsa",
        "inputs": EVENT_STREAM_ECDSA_INPUTS,
        "injectors": {},
        "managed": True,
        "description": (
            "Credential for Event Streams that use Elliptic Curve DSA. "
            "This requires a public key and the headers that carry "
            "the signature."
        ),
    },
    {
        "name": enums.CustomEventStreamCredentialType.GITLAB,
        "namespace": "event_stream",
        "kind": "gitlab",
        "inputs": EVENT_STREAM_GITLAB_INPUTS,
        "injectors": {},
        "managed": True,
        "description": (
            "Credential for Gitlab Event Streams. This is a specialization of "
            "the Token authentication with the X-Gitlab-Token header."
        ),
    },
    {
        "name": enums.CustomEventStreamCredentialType.GITHUB,
        "namespace": "event_stream",
        "kind": "github",
        "inputs": EVENT_STREAM_GITHUB_INPUTS,
        "injectors": {},
        "managed": True,
        "description": (
            "Credential for Github EventStream. This is a specialization of "
            "the HMAC authentication which only requires a secret to be "
            "provided."
        ),
    },
    {
        "name": enums.CustomEventStreamCredentialType.SNOW,
        "namespace": "event_stream",
        "kind": "snow",
        "inputs": EVENT_STREAM_SNOW_INPUTS,
        "injectors": {},
        "managed": True,
        "description": (
            "Credential for ServiceNow Event Stream. This is a "
            "specialization of the Token authentication which "
            "only requires a token to be provided."
        ),
    },
    {
        "name": enums.CustomEventStreamCredentialType.DYNATRACE,
        "namespace": "event_stream",
        "kind": "dynatrace",
        "inputs": EVENT_STREAM_DYNATRACE_INPUTS,
        "injectors": {},
        "managed": True,
        "description": (
            "Credential for Dynatrace Event Stream. This is a clone of "
            "the Basic authentication."
        ),
    },
]


def populate_credential_types(
    credential_types: list[dict],
) -> list[models.CredentialType]:
    created_credential_types = []

    for credential_type_data in credential_types:
        new_type, created = models.CredentialType.objects.get_or_create(
            name=credential_type_data["name"],
            defaults={
                "description": credential_type_data.get("description", ""),
                "namespace": credential_type_data.get("namespace"),
                "kind": credential_type_data.get("kind", "cloud"),
                "inputs": credential_type_data.get("inputs", {}),
                "injectors": credential_type_data.get("injectors", {}),
                "managed": credential_type_data.get("managed", True),
            },
        )
        if created:
            created_credential_types.append(new_type)

    return created_credential_types


class Command(BaseCommand):
    help = "Seed database with initial data."

    @transaction.atomic
    def handle(self, *args, **options):
        settings_registry.persist_registry_data()
        self._preload_credential_types()
        self._copy_registry_credentials()
        self._copy_scm_credentials()
        self._create_org_roles()
        self._create_obj_roles()
        self._remove_deprecated_credential_kinds()
        enable_redis_prefix()

    def _remove_deprecated_credential_kinds(self):
        """Remove old credential types which are deprecated."""
        for credential_type in models.CredentialType.objects.filter(
            kind__in=DEPRECATED_CREDENTIAL_KINDS
        ).all():
            credential_type.delete()

    def _preload_credential_types(self):
        for credential_type in populate_credential_types(CREDENTIAL_TYPES):
            self.stdout.write(
                f"New credential type {credential_type.name} is added."
            )

    def _copy_registry_credentials(self):
        credentials = models.Credential.objects.filter(
            credential_type=enums.CredentialType.REGISTRY
        ).all()
        if not credentials:
            return

        cred_type = models.CredentialType.objects.filter(
            name=enums.DefaultCredentialType.REGISTRY
        ).first()
        for cred in credentials:
            de = models.DecisionEnvironment.objects.filter(
                credential=cred
            ).first()
            host = "quay.io"
            if de:
                image_url = (
                    de.image_url.replace("http://", "")
                    .replace("https://", "")
                    .replace("//", "")
                )
                host = urlparse(f"//{image_url}").hostname
            inputs = {
                "host": host,
                "username": cred.username,
                "password": cred.secret.get_secret_value(),
            }
            eda_cred, created = models.EdaCredential.objects.get_or_create(
                name=cred.name,
                defaults={
                    "description": cred.description,
                    "managed": False,
                    "credential_type": cred_type,
                    "inputs": inputs_to_store(inputs),
                },
            )
            if created:
                models.DecisionEnvironment.objects.filter(
                    credential=cred
                ).update(eda_credential=eda_cred, credential=None)
                cred.delete()
            else:
                info_msg = (
                    f"Registry Credential {cred.name} already converted to "
                    "EdaCredential. Skip the duplicated one."
                )
                LOGGER.info(info_msg)

        self.stdout.write(
            "All REGISTRY credentials are converted to Container Registry "
            "eda-credentials"
        )

    def _copy_scm_credentials(self):
        types = [enums.CredentialType.GITHUB, enums.CredentialType.GITLAB]
        credentials = models.Credential.objects.filter(
            credential_type__in=types
        ).all()
        if not credentials:
            return

        cred_type = models.CredentialType.objects.filter(
            name=enums.DefaultCredentialType.SOURCE_CONTROL
        ).first()
        for cred in credentials:
            inputs = {
                "username": cred.username,
                "password": cred.secret.get_secret_value(),
            }
            eda_cred, created = models.EdaCredential.objects.get_or_create(
                name=cred.name,
                defaults={
                    "description": cred.description,
                    "managed": False,
                    "credential_type": cred_type,
                    "inputs": inputs_to_store(inputs),
                },
            )
            if created:
                models.Project.objects.filter(credential=cred).update(
                    eda_credential=eda_cred, credential=None
                )
                cred.delete()
            else:
                info_msg = (
                    f"Git Credential {cred.name} already converted to "
                    "EdaCredential. Skip the duplicated one."
                )
                LOGGER.info(info_msg)

        self.stdout.write(
            "All GITHUB and GITLAB credentials are converted to Source "
            "Control eda-credentials"
        )

    def _create_org_roles(self):
        org_ct = ContentType.objects.get(model="organization")
        created = updated = 0
        for role_data in ORG_ROLES:
            data = {
                "name": role_data["name"],
                "description": role_data["description"],
                "content_type": org_ct,
                "managed": True,
            }
            permissions = []
            for resource_type, actions in role_data["permissions"].items():
                model_permissions = list(
                    DABPermission.objects.filter(
                        codename__in=[
                            f'{action}_{resource_type.replace("_", "")}'
                            for action in actions
                        ],
                    )
                )
                if len(model_permissions) != len(actions):
                    raise ImproperlyConfigured(
                        f'Permission "{resource_type}" and one of '
                        f'"{actions}" actions is missing in the database, '
                        f"found {[p.codename for p in model_permissions]}."
                    )
                permissions.extend(model_permissions)
            try:
                role = RoleDefinition.objects.get(
                    Q(name=role_data["name"])
                    | Q(name=role_data["name"].split()[1])
                )
                for key, value in data.items():
                    setattr(role, key, value)
                role.save()
                updated += 1
                role.permissions.set(permissions)
                self.stdout.write(
                    'Updated role "{0}" with {1} permissions '
                    "to {2} resources".format(
                        role_data["name"],
                        len(permissions),
                        len(role_data["permissions"]),
                    )
                )
            except RoleDefinition.DoesNotExist:
                role = RoleDefinition.objects.create(**data)
                created += 1
                role.permissions.set(permissions)
                self.stdout.write(
                    'Created role "{0}" with {1} permissions '
                    "to {2} resources".format(
                        role_data["name"],
                        len(permissions),
                        len(role_data["permissions"]),
                    )
                )
        if updated:
            self.stdout.write(f"Updated {updated} organization roles.")
        if created:
            self.stdout.write(f"Created {created} organization roles.")

    def _create_permissions_for_content_type(self, ct=None) -> list:
        return [
            p
            for p in DABPermission.objects.filter(content_type=ct)
            if not p.codename.startswith("add_")
        ]

    def _create_obj_roles(self):
        for cls in permission_registry.all_registered_models:
            ct = ContentType.objects.get_for_model(cls)
            parent_model = permission_registry.get_parent_model(cls)
            # ignore if the model is organization, covered by org roles
            # or child model, inherits permissions from parent model
            if cls._meta.model_name == "organization" or (
                parent_model
                and parent_model._meta.model_name != "organization"
            ):
                continue
            permissions = self._create_permissions_for_content_type(ct)
            desc = f"Has all permissions to a single {cls._meta.verbose_name}"
            # parent model should add permissions related to its child models
            child_models = permission_registry.get_child_models(cls)
            child_names = []
            for _, child_model in child_models:
                child_ct = ContentType.objects.get_for_model(child_model)
                permissions.extend(
                    self._create_permissions_for_content_type(child_ct)
                )
                child_names.append(child_model._meta.verbose_name)
            if child_names:
                desc += f" and its child resources - {', '.join(child_names)}"  # noqa: E501

            # create resource admin role
            role, created = RoleDefinition.objects.update_or_create(
                name=f"{cls._meta.verbose_name.title()} Admin",
                defaults={
                    "description": desc,
                    "content_type": ct,
                    "managed": True,
                },
            )
            role.permissions.set(permissions)
            if created:
                self.stdout.write(
                    f"Added role {role.name} with {len(permissions)} "
                    "permissions to itself"
                )

            # create resource use role
            # ignore team model as it makes no sense to have Use role for it
            # and should be managed by Admin users only
            if cls._meta.model_name != "team":
                (
                    use_role,
                    use_role_created,
                ) = RoleDefinition.objects.update_or_create(
                    name=f"{cls._meta.verbose_name.title()} Use",
                    defaults={
                        "description": f"Has use permissions to a single {cls._meta.verbose_name}",  # noqa: E501
                        "content_type": ct,
                        "managed": True,
                    },
                )
                use_permissions = [
                    perm
                    for perm in permissions
                    if perm.codename.startswith("view_")
                ]
                use_role.permissions.set(use_permissions)
                if use_role_created:
                    self.stdout.write(
                        f"Added role {use_role.name} with "
                        f"{len(use_permissions)} permissions to itself"
                    )

                # create org-level admin roles for each resource type
                (
                    org_role,
                    org_role_created,
                ) = RoleDefinition.objects.update_or_create(
                    name=f"Organization {cls._meta.verbose_name.title()} Admin",  # noqa: E501
                    defaults={
                        "description": f"Has all permissions to {cls._meta.verbose_name}s within an organization",  # noqa: E501
                        "content_type": ContentType.objects.get(
                            model="organization"
                        ),
                        "managed": True,
                    },
                )
                permissions.extend(
                    DABPermission.objects.filter(
                        content_type=ct, codename__startswith="add_"
                    )
                )
                org_role.permissions.set(permissions)
                if org_role_created:
                    self.stdout.write(
                        f"Added role {org_role.name} with {len(permissions)} "
                        "permissions to itself"
                    )

            # Special case to create team member role
            if cls._meta.model_name == "team":
                member_permissions = [
                    p
                    for p in permissions
                    if p.codename in ("view_team", "member_team")
                ]
                desc = "Inherits permissions assigned to this team"
                role, created = RoleDefinition.objects.update_or_create(
                    name="Team Member",
                    defaults={
                        "description": desc,
                        "content_type": ct,
                        "managed": True,
                    },
                )
                role.permissions.set(member_permissions)
                if created:
                    self.stdout.write(
                        f"Added role {role.name} with "
                        f"{len(member_permissions)} permissions to itself"
                    )
