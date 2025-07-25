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
import os

from ansible_base.rbac import permission_registry
from ansible_base.rbac.models import DABPermission, RoleDefinition
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q

from aap_eda.conf import settings_registry
from aap_eda.core import enums, models
from aap_eda.core.models.utils import get_default_organization
from aap_eda.core.tasking import enable_redis_prefix
from aap_eda.core.utils.credentials import inputs_to_store
from aap_eda.settings import features

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
LABEL_PATH_TO_AUTH = "Path to Auth"
LABEL_CLIENT_CERTIFICATE = "Client Certificate"
LABEL_CLIENT_SECRET = "Client Secret"
LABEL_CLIENT_ID = "Client ID"
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
            "activation": CRUD + ["enable", "disable", "restart"],
            "rulebook_process": ["view"],
            "audit_rule": ["view"],
            "organization": ["view", "change", "delete"],
            "team": CRUD + ["member"],
            "project": CRUD + ["sync"],
            "rulebook": ["view"],
            "decision_environment": CRUD,
            "eda_credential": CRUD,
            "credential_input_source": CRUD,
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
            "activation": ["add", "view", "change"],
            "rulebook_process": ["view"],
            "audit_rule": ["view"],
            "organization": ["view"],
            "team": ["view"],
            "project": ["add", "view", "change"],
            "rulebook": ["view"],
            "decision_environment": ["add", "view", "change"],
            "eda_credential": ["add", "view", "change"],
            "credential_input_source": ["add", "view", "change"],
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
                "change",
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
            "credential_input_source": ["add", "view", "change"],
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
            "credential_input_source": ["view"],
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
            "credential_input_source": ["view"],
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
            "credential_input_source": ["view"],
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
        {
            "id": "request_timeout",
            "label": ("Request Timeout"),
            "type": "string",
            "secret": False,
            "default": "10",
            "help_text": (
                "Specify the timeout Ansible should use in requests to"
                "the host. Defaults to 10s",
            ),
        },
    ],
    "required": ["host"],
}

AAP_INJECTORS = {
    "extra_vars": {
        "aap_hostname": "{{host}}",
        "aap_username": "{{username}}",
        "aap_password": "{{password}}",
        "aap_token": "{{oauth_token}}",
        "aap_request_timeout": "{{request_timeout}}",
        "aap_verify_ssl": "{{verify_ssl}}",
    },
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
        "CONTROLLER_REQUEST_TIMEOUT": "{{request_timeout}}",
        "AAP_HOSTNAME": "{{host}}",
        "AAP_USERNAME": "{{username}}",
        "AAP_PASSWORD": "{{password}}",
        "AAP_VERIFY_SSL": "{{verify_ssl}}",
        "AAP_TOKEN": "{{oauth_token}}",
        "AAP_REQUEST_TIMEOUT": "{{request_timeout}}",
    },
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
            "label": LABEL_CLIENT_ID,
            "type": "string",
            "help_text": "The Client ID from the Authorization Server.",
        },
        {
            "id": "client_secret",
            "label": LABEL_CLIENT_SECRET,
            "type": "string",
            "secret": True,
            "help_text": "The Client Secret from the Authorization Server.",
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

POSTGRES_CREDENTIAL_INPUTS = {
    "fields": [
        {
            "id": "postgres_db_host",
            "label": "Postgres DB Host",
            "help_text": "Postgres DB Server",
        },
        {
            "id": "postgres_db_port",
            "label": "Postgres DB Port",
            "help_text": "Postgres DB Port",
            "default": "5432",
        },
        {
            "id": "postgres_db_name",
            "label": "Postgres DB Name",
            "help_text": "Postgres Database name",
        },
        {
            "id": "postgres_db_user",
            "label": "Postgres DB User",
            "help_text": "Postgres Database user",
        },
        {
            "id": "postgres_db_password",
            "label": "Postgres DB Password",
            "help_text": "Postgres Database password",
            "secret": True,
        },
        {
            "id": "postgres_sslmode",
            "label": "Postgres SSL Mode",
            "help_text": "Postgres SSL Mode",
            "choices": [
                "disable",
                "allow",
                "prefer",
                "require",
                "verify-ca",
                "verify-full",
            ],
            "default": "prefer",
        },
        {
            "id": "postgres_sslcert",
            "label": "Postgres SSL Certificate",
            "help_text": "Postgres SSL Certificate",
            "multiline": True,
            "default": "",
        },
        {
            "id": "postgres_sslkey",
            "label": "Postgres SSL Key",
            "help_text": "Postgres SSL Key",
            "multiline": True,
            "secret": True,
            "default": "",
        },
        {
            "id": "postgres_sslpassword",
            "label": "Postgres SSL Password",
            "help_text": "Postgres SSL Password for key",
            "secret": True,
            "default": "",
        },
        {
            "id": "postgres_sslrootcert",
            "label": "Postgres SSL Root Certificate",
            "help_text": "Postgres SSL Root Certificate",
            "multiline": True,
            "default": "",
        },
    ]
}

ANALYTICS_CREDENTIAL_OAUTH_INPUTS = {
    "fields": [
        {
            "id": "auth_type",
            "label": "Analytics Authentication Type",
            "type": "string",
            "default": "oauth",
            "hidden": True,
        },
        {
            "id": "client_id",
            "label": LABEL_CLIENT_ID,
            "type": "string",
            "help_text": "The Client ID from the Authorization Server.",
        },
        {
            "id": "client_secret",
            "label": LABEL_CLIENT_SECRET,
            "type": "string",
            "secret": True,
            "help_text": "The Client Secret from the Authorization Server.",
        },
        {
            "id": "gather_interval",
            "label": "Analytics Gather Interval",
            "type": "string",
            "help_text": "The time interval between each collection (secs)",
            "default": "14400",
        },
        {
            "id": "insights_tracking_state",
            "label": "Insights Tracking State",
            "type": "boolean",
            "default": False,
            "help_text": (
                "Enables the service to gather data on automation "
                "and send it to Automation Analytics"
            ),
        },
    ],
    "required": ["auth_type", "client_id", "client_secret"],
}

ANALYTICS_CREDENTIAL_BASIC_INPUTS = {
    "fields": [
        {
            "id": "auth_type",
            "label": "Analytics Authentication Type",
            "type": "string",
            "default": "basic",
            "hidden": True,
        },
        {
            "id": "username",
            "label": "Username",
            "type": "string",
            "help_text": "The username of REDHAT or SUBSCRIPTIONS",
        },
        {
            "id": "password",
            "label": "Password",
            "type": "string",
            "secret": True,
            "help_text": "The password of REDHAT or SUBSCRIPTIONS",
        },
        {
            "id": "gather_interval",
            "label": "Analytics Gather Interval",
            "type": "string",
            "help_text": "The time interval between each collection (secs)",
            "default": "14400",
        },
        {
            "id": "insights_tracking_state",
            "label": "Insights Tracking State",
            "type": "boolean",
            "default": False,
            "help_text": (
                "Enables the service to gather data on automation "
                "and send it to Automation Analytics"
            ),
        },
    ],
    "required": ["auth_type", "username", "password"],
}

POSTGRES_CREDENTIAL_INJECTORS = {
    "extra_vars": {
        "postgres_db_host": "{{ postgres_db_host }}",
        "postgres_db_port": "{{ postgres_db_port }}",
        "postgres_db_name": "{{ postgres_db_name }}",
        "postgres_db_user": "{{ postgres_db_user }}",
        "postgres_db_password": "{{ postgres_db_password }}",
        "postgres_sslpassword": "{{ postgres_sslpassword | default(None) }}",
        "postgres_sslmode": "{{ postgres_sslmode }}",
    },
    "file": {
        "template.postgres_sslcert": "{{ postgres_sslcert }}",
        "template.postgres_sslrootcert": "{{ postgres_sslrootcert }}",
        "template.postgres_sslkey": "{{ postgres_sslkey }}",
    },
}

HASHICORP_SHARED_FIELDS = [
    {
        "id": "url",
        "label": "Server URL",
        "type": "string",
        "format": "url",
        "help_text": "The URL to the HashiCorp Vault",
    },
    {
        "id": "token",
        "label": "Token",
        "type": "string",
        "secret": True,
        "help_text": (
            "The access token used to authenticate to the Vault server"
        ),
    },
    {
        "id": "cacert",
        "label": "CA Certificate",
        "type": "string",
        "multiline": True,
        "help_text": (
            "The CA certificate used to verify the SSL "
            "certificate of the Vault server"
        ),
    },
    {
        "id": "role_id",
        "label": "AppRole role_id",
        "type": "string",
        "multiline": False,
        "help_text": "The Role ID for AppRole Authentication",
    },
    {
        "id": "secret_id",
        "label": "AppRole secret_id",
        "type": "string",
        "multiline": False,
        "secret": True,
        "help_text": "The Secret ID for AppRole Authentication",
    },
    {
        "id": "client_cert_public",
        "label": LABEL_CLIENT_CERTIFICATE,
        "type": "string",
        "multiline": True,
        "help_text": (
            "The PEM-encoded client certificate used for TLS "
            "client authentication. This should include the "
            "certificate and any intermediate certififcates."
        ),
    },
    {
        "id": "client_cert_private",
        "label": "Client Certificate Key",
        "type": "string",
        "multiline": True,
        "secret": True,
        "help_text": (
            "The certificate private key used for TLS "
            "client authentication."
        ),
    },
    {
        "id": "client_cert_role",
        "label": "TLS Authentication Role",
        "type": "string",
        "multiline": False,
        "help_text": (
            "The role configured in Hashicorp Vault for TLS "
            "client authentication. If not provided, Hashicorp "
            "Vault may assign roles based on the certificate used."
        ),
    },
    {
        "id": "namespace",
        "label": "Namespace name (Vault Enterprise only)",
        "type": "string",
        "multiline": False,
        "help_text": (
            "Name of the namespace to use when authenticate "
            "and retrieve secrets"
        ),
    },
    {
        "id": "kubernetes_role",
        "label": "Kubernetes role",
        "type": "string",
        "multiline": False,
        "help_text": (
            "The Role for Kubernetes Authentication. This is the "
            "named role, configured in Vault server, for AWX pod "
            "auth policies. see "
            "https://www.vaultproject.io/docs/auth/"
            "kubernetes#configuration"
        ),
    },
    {
        "id": "username",
        "label": "Username",
        "type": "string",
        "secret": False,
        "help_text": "Username for user authentication.",
    },
    {
        "id": "password",
        "label": "Password",
        "type": "string",
        "secret": True,
        "help_text": "Password for user authentication.",
    },
    {
        "id": "default_auth_path",
        "label": LABEL_PATH_TO_AUTH,
        "type": "string",
        "multiline": False,
        "default": "approle",
        "help_text": (
            "The Authentication path to use if one isn't "
            "provided in the metadata when linking to an "
            "input field. Defaults to 'approle'"
        ),
    },
]

HASHICORP_LOOKUP_EXTRA_FIELDS = [
    {
        "id": "api_version",
        "label": "API Version",
        "type": "string",
        "choices": ["v1", "v2"],
        "help_text": (
            "API v1 is for static key/value lookups.  API v2 is for versioned "
            "key/value lookups."
        ),
        "default": "v1",
    }
]

HASHICORP_VAULT_SECRET_LOOKUP_INPUTS = {
    "fields": HASHICORP_SHARED_FIELDS + HASHICORP_LOOKUP_EXTRA_FIELDS,
    "metadata": [
        {
            "id": "secret_backend",
            "label": "Name of Secret Backend",
            "type": "string",
            "help_text": (
                "The name of the kv secret backend (if left empty, "
                "the first segment of the secret path will be used)."
            ),
        },
        {
            "id": "secret_path",
            "label": "Path to Secret",
            "type": "string",
            "help_text": (
                "The path to the secret stored in the secret backend "
                "e.g, /some/secret/. It is recommended that you use "
                "the secret backend field to identify the storage "
                "backend and to use this field for locating a specific "
                "secret within that store. However, if you prefer to "
                "fully identify both the secret backend and one of its "
                "secrets using only this field, join their locations "
                "into a single path without any additional separators, "
                "e.g, /location/of/backend/some/secret."
            ),
        },
        {
            "id": "auth_path",
            "label": LABEL_PATH_TO_AUTH,
            "type": "string",
            "multiline": False,
            "help_text": (
                "The path where the Authentication method is "
                "mounted e.g, approle"
            ),
        },
        {
            "id": "secret_key",
            "label": "Key Name",
            "type": "string",
            "help_text": "The name of the key to look up in the secret.",
        },
        {
            "id": "secret_version",
            "label": "Secret Version (v2 only)",
            "type": "string",
            "help_text": (
                "Used to specify a specific secret version (if left "
                "empty, the latest version will be used)."
            ),
        },
    ],
    "required": ["url", "secret_path", "api_version", "secret_key"],
}

AWS_SECRETS_MANAGER_LOOKUP_INPUTS = {
    "fields": [
        {"id": "aws_access_key", "label": "AWS Access Key", "type": "string"},
        {
            "id": "aws_secret_key",
            "label": "AWS Secret Key",
            "type": "string",
            "secret": True,
        },
    ],
    "metadata": [
        {
            "id": "region_name",
            "label": "AWS Secrets Manager Region",
            "type": "string",
            "help_text": "Region which the secrets manager is located",
        },
        {"id": "secret_name", "label": "AWS Secret Name", "type": "string"},
    ],
    "required": [
        "aws_access_key",
        "aws_secret_key",
        "region_name",
        "secret_name",
    ],
}


CENTRIFY_VAULT_CREDENTIAL_PROVIDER_LOOKUP_INPUTS = {
    "fields": [
        {
            "id": "url",
            "label": "Centrify Tenant URL",
            "type": "string",
            "help_text": "Centrify Tenant URL",
            "format": "url",
        },
        {
            "id": "client_id",
            "label": "Centrify API User",
            "type": "string",
            "help_text": (
                "Centrify API User, having necessary "
                "permissions as mentioned in support doc"
            ),
        },
        {
            "id": "client_password",
            "label": "Centrify API Password",
            "type": "string",
            "help_text": (
                "Password of Centrify API User with necessary permissions"
            ),
            "secret": True,
        },
        {
            "id": "oauth_application_id",
            "label": "OAuth2 Application ID",
            "type": "string",
            "help_text": (
                "Application ID of the configured "
                "OAuth2 Client (defaults to 'awx')"
            ),
            "default": "awx",
        },
        {
            "id": "oauth_scope",
            "label": "OAuth2 Scope",
            "type": "string",
            "help_text": (
                "Scope of the configured OAuth2 Client (defaults to 'awx')"
            ),
            "default": "awx",
        },
    ],
    "metadata": [
        {
            "id": "account-name",
            "label": "Account Name",
            "type": "string",
            "help_text": (
                "Local system account or Domain account "
                "name enrolled in Centrify Vault. eg. "
                "(root or DOMAIN/Administrator)"
            ),
        },
        {
            "id": "system-name",
            "label": "System Name",
            "type": "string",
            "help_text": "Machine Name enrolled with in Centrify Portal",
        },
    ],
    "required": [
        "url",
        "account-name",
        "system-name",
        "client_id",
        "client_password",
    ],
}


HASHICORP_VAULT_SIGNED_SSH_INPUTS = {
    "fields": HASHICORP_SHARED_FIELDS,
    "metadata": [
        {
            "id": "public_key",
            "label": "Unsigned Public Key",
            "type": "string",
            "multiline": True,
        },
        {
            "id": "secret_path",
            "label": "Path to Secret",
            "type": "string",
            "help_text": (
                "The path to the secret stored in the secret backend "
                "e.g, /some/secret/. It is recommended that you use "
                "the secret backend field to identify the storage backend "
                "and to use this field for locating a specific secret "
                "within that store. However, if you prefer to fully identify "
                "both the secret backend and one of its secrets using only "
                "this field, join their locations into a single path without "
                "any additional separators, "
                "e.g, /location/of/backend/some/secret."
            ),
        },
        {
            "id": "auth_path",
            "label": LABEL_PATH_TO_AUTH,
            "type": "string",
            "multiline": False,
            "help_text": (
                "The path where the Authentication method is "
                "mounted e.g, approle"
            ),
        },
        {
            "id": "role",
            "label": "Role Name",
            "type": "string",
            "help_text": "The name of the role used to sign.",
        },
        {
            "id": "valid_principals",
            "label": "Valid Principals",
            "type": "string",
            "help_text": (
                "Valid principals (either usernames or hostnames) that the "
                "certificate should be signed for."
            ),
        },
    ],
    "required": ["url", "secret_path", "public_key", "role"],
}

THYCOTIC_DEVOPS_SECRETS_VAULT_INPUTS = {
    "fields": [
        {
            "id": "tenant",
            "label": "Tenant",
            "help_text": (
                'The tenant e.g. "ex" when the URL '
                "is https://ex.secretsvaultcloud.com"
            ),
            "type": "string",
        },
        {
            "id": "tld",
            "label": "Top-level Domain (TLD)",
            "help_text": (
                'The TLD of the tenant e.g. "com" when the '
                "URL is https://ex.secretsvaultcloud.com"
            ),
            "choices": ["ca", "com", "com.au", "eu"],
            "default": "com",
        },
        {"id": "client_id", "label": LABEL_CLIENT_ID, "type": "string"},
        {
            "id": "client_secret",
            "label": LABEL_CLIENT_SECRET,
            "type": "string",
            "secret": True,
        },
    ],
    "metadata": [
        {
            "id": "path",
            "label": "Secret Path",
            "type": "string",
            "help_text": "The secret path e.g. /test/secret1",
        },
        {
            "id": "secret_field",
            "label": "Secret Field",
            "help_text": "The field to extract from the secret",
            "type": "string",
        },
        {
            "id": "secret_decoding",
            "label": "Should the secret be base64 decoded?",
            "help_text": (
                "Specify whether the secret should be base64 decoded, "
                "typically used for storing files, such as SSH keys"
            ),
            "choices": ["No Decoding", "Decode Base64"],
            "type": "string",
            "default": "No Decoding",
        },
    ],
    "required": [
        "tenant",
        "client_id",
        "client_secret",
        "path",
        "secret_field",
        "secret_decoding",
    ],
}

THYCOTIC_SECRET_SERVER_INPUTS = {
    "fields": [
        {
            "id": "server_url",
            "label": "Secret Server URL",
            "help_text": (
                "The Base URL of Secret Server e.g. "
                "https://myserver/SecretServer or "
                "https://mytenant.secretservercloud.com"
            ),
            "type": "string",
        },
        {
            "id": "username",
            "label": "Username",
            "help_text": "The (Application) user username",
            "type": "string",
        },
        {
            "id": "domain",
            "label": "Domain",
            "help_text": "The (Application) user domain",
            "type": "string",
        },
        {
            "id": "password",
            "label": "Password",
            "help_text": "The corresponding password",
            "type": "string",
            "secret": True,
        },
    ],
    "metadata": [
        {
            "id": "secret_id",
            "label": "Secret ID",
            "help_text": "The integer ID of the secret",
            "type": "string",
        },
        {
            "id": "secret_field",
            "label": "Secret Field",
            "help_text": "The field to extract from the secret",
            "type": "string",
        },
    ],
    "required": [
        "server_url",
        "username",
        "password",
        "secret_id",
        "secret_field",
    ],
}

CYBERARK_CENTRAL_CREDENTIAL_PROVIDER_LOOKUP_INPUTS = {
    "fields": [
        {
            "id": "url",
            "label": "CyberArk CCP URL",
            "type": "string",
            "format": "url",
        },
        {
            "id": "webservice_id",
            "label": "Web Service ID",
            "type": "string",
            "help_text": (
                "The CCP Web Service ID. Leave "
                "blank to default to AIMWebService."
            ),
        },
        {
            "id": "app_id",
            "label": "Application ID",
            "type": "string",
            "secret": True,
        },
        {
            "id": "client_key",
            "label": "Client Key",
            "type": "string",
            "secret": True,
            "multiline": True,
        },
        {
            "id": "client_cert",
            "label": LABEL_CLIENT_CERTIFICATE,
            "type": "string",
            "secret": True,
            "multiline": True,
        },
        {
            "id": "verify",
            "label": "Verify SSL Certificates",
            "type": "boolean",
            "default": True,
        },
    ],
    "metadata": [
        {
            "id": "object_query",
            "label": "Object Query",
            "type": "string",
            "help_text": (
                "Lookup query for the object. Ex: "
                "Safe=TestSafe;Object=testAccountName123"
            ),
        },
        {
            "id": "object_query_format",
            "label": "Object Query Format",
            "type": "string",
            "default": "Exact",
            "choices": ["Exact", "Regexp"],
        },
        {
            "id": "object_property",
            "label": "Object Property",
            "type": "string",
            "help_text": (
                "The property of the object to return. Available "
                "properties: Username, Password and Address."
            ),
        },
        {
            "id": "reason",
            "label": "Reason",
            "type": "string",
            "help_text": (
                "Object request reason. This is only needed if it "
                "is required by the object's policy."
            ),
        },
    ],
    "required": ["url", "app_id", "object_query"],
}

CYBERARK_CONJUR_SECRETS_MANAGER_LOOKUP_INPUTS = {
    "fields": [
        {
            "id": "url",
            "label": "Conjur URL",
            "type": "string",
            "format": "url",
        },
        {
            "id": "api_key",
            "label": "API Key",
            "type": "string",
            "secret": True,
        },
        {"id": "account", "label": "Account", "type": "string"},
        {"id": "username", "label": "Username", "type": "string"},
        {
            "id": "cacert",
            "label": "Public Key Certificate",
            "type": "string",
            "multiline": True,
        },
    ],
    "metadata": [
        {
            "id": "secret_path",
            "label": "Secret Identifier",
            "type": "string",
            "help_text": (
                "The identifier for the secret e.g., /some/identifier"
            ),
        },
        {
            "id": "secret_version",
            "label": "Secret Version",
            "type": "string",
            "help_text": (
                "Used to specify a specific secret version (if left empty, "
                "the latest version will be used)."
            ),
        },
    ],
    "required": ["url", "api_key", "account", "username"],
}

MICROSOFT_AZURE_KEY_VAULT_INPUTS = {
    "fields": [
        {
            "id": "url",
            "label": "Vault URL (DNS Name)",
            "type": "string",
            "format": "url",
        },
        {"id": "client", "label": LABEL_CLIENT_ID, "type": "string"},
        {
            "id": "secret",
            "label": LABEL_CLIENT_SECRET,
            "type": "string",
            "secret": True,
        },
        {"id": "tenant", "label": "Tenant ID", "type": "string"},
        {
            "id": "cloud_name",
            "label": "Cloud Environment",
            "help_text": "Specify which azure cloud environment to use.",
            "choices": [
                "AzureCloud",
                "AzureGermanCloud",
                "AzureChinaCloud",
                "AzureUSGovernment",
            ],
            "default": "AzureCloud",
        },
    ],
    "metadata": [
        {
            "id": "secret_field",
            "label": "Secret Name",
            "type": "string",
            "help_text": "The name of the secret to look up.",
        },
        {
            "id": "secret_version",
            "label": "Secret Version",
            "type": "string",
            "help_text": (
                "Used to specify a specific secret version "
                "(if left empty, the latest version will be used)."
            ),
        },
    ],
    "required": ["url", "secret_field"],
}

GITHUB_APP_INPUTS = {
    "fields": [
        {
            "id": "github_api_url",
            "label": "GitHub API endpoint URL",
            "type": "string",
            "help_text": (
                "Specify the GitHub API URL here. In the case of an "
                "Enterprise: https://gh.your.org/api/v3 (self-hosted) "
                "or https://api.SUBDOMAIN.ghe.com (cloud)"
            ),
            "default": "https://api.github.com",
        },
        {
            "id": "app_or_client_id",
            "label": "GitHub App ID",
            "type": "string",
            "help_text": (
                "The GitHub App ID created by the GitHub Admin. Example "
                "App ID: 1121547 found on https://github.com/settings/apps/ "
                "required for creating a JWT token for authentication."
            ),
        },
        {
            "id": "install_id",
            "label": "GitHub App Installation ID",
            "type": "string",
            "help_text": (
                "The Installation ID from the GitHub App installation "
                "generated by the GitHub Admin. Example: 59980338 "
                "extracted from the installation link "
                "https://github.com/settings/installations/59980338 "
                "required for creating a limited GitHub app token."
            ),
        },
        {
            "id": "private_rsa_key",
            "label": "RSA Private Key",
            "type": "string",
            "format": "ssh_private_key",
            "secret": True,
            "multiline": True,
            "help_text": (
                "Paste the contents of the PEM file that the GitHub Admin "
                "provided to you with the app and installation IDs."
            ),
        },
    ],
    "metadata": [
        {
            "id": "description",
            "label": "Description (Optional)",
            "type": "string",
            "help_text": "To be removed after UI is updated",
        }
    ],
    "required": ["app_or_client_id", "install_id", "private_rsa_key"],
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
    {
        "name": enums.DefaultCredentialType.POSTGRES,
        "kind": "cloud",
        "namespace": "postgres",
        "inputs": POSTGRES_CREDENTIAL_INPUTS,
        "injectors": POSTGRES_CREDENTIAL_INJECTORS,
        "managed": True,
    },
    {
        "name": enums.AnalyticsCredentialType.BASIC,
        "namespace": "analytics",
        "kind": "user-pass",
        "inputs": ANALYTICS_CREDENTIAL_BASIC_INPUTS,
        "injectors": {},
        "managed": True,
        "description": (
            "Credential for analytics that use for authentication."
        ),
    },
    {
        "name": enums.AnalyticsCredentialType.OAUTH,
        "namespace": "analytics",
        "kind": "service-account",
        "inputs": ANALYTICS_CREDENTIAL_OAUTH_INPUTS,
        "injectors": {},
        "managed": True,
        "description": (
            "Credential for analytics that use for authentication."
        ),
    },
    {
        "name": enums.DefaultCredentialType.HASHICORP_LOOKUP,
        "namespace": "hashivault_kv",
        "inputs": HASHICORP_VAULT_SECRET_LOOKUP_INPUTS,
        "kind": "external",
        "injectors": {},
        "managed": True,
    },
    {
        "name": enums.DefaultCredentialType.HASHICORP_SSH,
        "namespace": "hashivault_ssh",
        "inputs": HASHICORP_VAULT_SIGNED_SSH_INPUTS,
        "kind": "external",
        "injectors": {},
        "managed": True,
    },
    {
        "name": enums.DefaultCredentialType.AWS_SECRETS_LOOKUP,
        "namespace": "aws_secretsmanager_credential",
        "inputs": AWS_SECRETS_MANAGER_LOOKUP_INPUTS,
        "kind": "external",
        "injectors": {},
        "managed": True,
    },
    {
        "name": enums.DefaultCredentialType.CENTRIFY_VAULT_LOOKUP,
        "namespace": "centrify_vault_kv",
        "inputs": CENTRIFY_VAULT_CREDENTIAL_PROVIDER_LOOKUP_INPUTS,
        "kind": "external",
        "injectors": {},
        "managed": True,
    },
    {
        "name": enums.DefaultCredentialType.THYCOTIC_DSV,
        "namespace": "thycotic_dsv",
        "inputs": THYCOTIC_DEVOPS_SECRETS_VAULT_INPUTS,
        "kind": "external",
        "injectors": {},
        "managed": True,
    },
    {
        "name": enums.DefaultCredentialType.THYCOTIC_SECRET_SERVER,
        "namespace": "thycotic_tss",
        "inputs": THYCOTIC_SECRET_SERVER_INPUTS,
        "kind": "external",
        "injectors": {},
        "managed": True,
    },
    {
        "name": enums.DefaultCredentialType.CYBERARK_CENTRAL,
        "namespace": "aim",
        "inputs": CYBERARK_CENTRAL_CREDENTIAL_PROVIDER_LOOKUP_INPUTS,
        "kind": "external",
        "injectors": {},
        "managed": True,
    },
    {
        "name": enums.DefaultCredentialType.CYBERARK_CONJUR,
        "namespace": "conjur",
        "inputs": CYBERARK_CONJUR_SECRETS_MANAGER_LOOKUP_INPUTS,
        "kind": "external",
        "injectors": {},
        "managed": True,
    },
    {
        "name": enums.DefaultCredentialType.MSFT_AZURE_VAULT,
        "namespace": "azure_kv",
        "inputs": MICROSOFT_AZURE_KEY_VAULT_INPUTS,
        "kind": "external",
        "injectors": {},
        "managed": True,
    },
    {
        "name": enums.DefaultCredentialType.GITHUB_APP,
        "namespace": "github_app",
        "inputs": GITHUB_APP_INPUTS,
        "kind": "external",
        "injectors": {},
        "managed": True,
    },
]


def populate_credential_types(
    credential_types: list[dict],
) -> list[models.CredentialType]:
    created_credential_types = []

    for credential_type_data in credential_types:
        # Analytics credential types are only available when it's enabled
        if (
            not features.ANALYTICS
            and credential_type_data.get("name")
            in enums.SINGLETON_CREDENTIAL_TYPES
        ):
            continue

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
        self._update_postgres_credentials()
        self._create_org_roles()
        self._create_obj_roles()
        self._remove_deprecated_credential_kinds()
        enable_redis_prefix()

    @property
    def content_type_model(self):
        try:
            # DAB RBAC migrated to a custom type model, try to use that here
            return apps.get_model("dab_rbac", "DABContentType")
        except LookupError:
            # Fallback for older version of DAB, which just used ContentType
            return apps.get_model("contenttypes", "ContentType")

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

    def _update_postgres_credentials(self):
        cred_type = models.CredentialType.objects.get(
            name=enums.DefaultCredentialType.POSTGRES
        )
        _db_options = settings.DATABASES["default"].get("OPTIONS", {})
        inputs = {
            "postgres_db_host": settings.ACTIVATION_DB_HOST,
            "postgres_db_port": settings.DATABASES["default"]["PORT"],
            "postgres_db_name": settings.DATABASES["default"]["NAME"],
            "postgres_db_user": settings.DATABASES["default"]["USER"],
            "postgres_db_password": settings.DATABASES["default"]["PASSWORD"],
            "postgres_sslmode": _db_options.get("sslmode", "allow"),
            "postgres_sslcert": "",
            "postgres_sslkey": "",
            "postgres_sslrootcert": "",
        }

        if _db_options.get("sslcert", ""):
            inputs["postgres_sslcert"] = self._read_file(
                _db_options["sslcert"],
                "PGSSLCERT",
            )

        if _db_options.get("sslkey", ""):
            inputs["postgres_sslkey"] = self._read_file(
                _db_options["sslkey"], "PGSSLKEY"
            )

        if _db_options.get("sslrootcert", ""):
            inputs["postgres_sslrootcert"] = self._read_file(
                _db_options["sslrootcert"],
                "PGSSLROOTCERT",
            )

        models.EdaCredential.objects.update_or_create(
            name=settings.DEFAULT_SYSTEM_PG_NOTIFY_CREDENTIAL_NAME,
            defaults={
                "description": "Default PG Notify Credentials",
                "managed": True,
                "credential_type": cred_type,
                "inputs": inputs_to_store(inputs),
                "organization": get_default_organization(),
            },
        )

    def _read_file(self, name: str, key: str):
        if not os.path.exists(name):
            raise ImproperlyConfigured(f"Missing {key} file: {name}")
        with open(name) as f:
            return f.read()

    def _create_org_roles(self):
        org_ct = self.content_type_model.objects.get(model="organization")
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
            ct = self.content_type_model.objects.get_for_model(cls)
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
                child_ct = self.content_type_model.objects.get_for_model(
                    child_model
                )
                permissions.extend(
                    self._create_permissions_for_content_type(child_ct)
                )
                child_names.append(child_model._meta.verbose_name)
            if child_names:
                desc += f" and its child resources - {', '.join(child_names)}"  # noqa: E501

            # create resource admin role
            admin_role_name = f"{cls._meta.verbose_name.title()} Admin"
            if cls._meta.model_name == "project":
                admin_role_name = f"EDA {admin_role_name}"

            role, created = RoleDefinition.objects.update_or_create(
                name=admin_role_name,
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
                use_role_name = f"{cls._meta.verbose_name.title()} Use"
                if cls._meta.model_name == "project":
                    use_role_name = f"EDA {use_role_name}"

                (
                    use_role,
                    use_role_created,
                ) = RoleDefinition.objects.update_or_create(
                    name=use_role_name,
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
                org_role_name = (
                    f"Organization {cls._meta.verbose_name.title()} Admin"
                )
                if cls._meta.model_name == "project":
                    org_role_name = f"EDA {org_role_name}"

                (
                    org_role,
                    org_role_created,
                ) = RoleDefinition.objects.update_or_create(
                    name=org_role_name,
                    defaults={
                        "description": f"Has all permissions to {cls._meta.verbose_name}s within an organization",  # noqa: E501
                        "content_type": self.content_type_model.objects.get(
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
