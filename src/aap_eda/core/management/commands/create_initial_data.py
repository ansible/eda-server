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
from django.core.exceptions import ImproperlyConfigured
from django.core.management import BaseCommand
from django.db import transaction

from aap_eda.core import models

# FIXME(cutwater): Role descriptions were taken from the RBAC design document
#  and must be updated.
ROLES = [
    {
        "name": "Admin",
        "description": "Has all permissions",
        "permissions": {
            "activation": [
                "create",
                "read",
                "update",
                "delete",
                "enable",
                "disable",
                "restart",
            ],
            "activation_instance": ["read", "delete"],
            "audit_rule": ["read"],
            "audit_event": ["read"],
            "user": ["create", "read", "update", "delete"],
            "project": ["create", "read", "update", "delete"],
            "extra_var": ["create", "read", "update", "delete"],
            "rulebook": ["create", "read", "update", "delete"],
            "role": ["create", "read", "update", "delete"],
            "decision_environment": ["create", "read", "update", "delete"],
            "credential": ["create", "read", "update", "delete"],
            "event_stream": ["create", "read"],
            "credential_type": ["create", "read", "update", "delete"],
            "eda_credential": ["create", "read", "update", "delete"],
        },
    },
    {
        "name": "Editor",
        "description": "Has create and edit permissions.",
        "permissions": {
            "activation": ["create", "read", "update", "delete"],
            "activation_instance": ["read"],
            "audit_rule": ["read"],
            "audit_event": ["read"],
            "project": ["create", "read", "update", "delete"],
            "extra_var": ["create", "read", "update", "delete"],
            "rulebook": ["create", "read", "update", "delete"],
            "decision_environment": ["create", "read", "update", "delete"],
            "credential": ["create", "read", "update", "delete"],
            "event_stream": ["create", "read"],
            "credential_type": ["create", "read"],
            "eda_credential": ["create", "read"],
        },
    },
    {
        "name": "Contributor",
        "description": (
            "Has create and update permissions with an "
            "exception of users and roles. "
            "Has enable and disable rulebook activation permissions."
        ),
        "permissions": {
            "activation": [
                "create",
                "read",
                "update",
                "delete",
                "enable",
                "disable",
                "restart",
            ],
            "activation_instance": ["read", "delete"],
            "audit_rule": ["read"],
            "audit_event": ["read"],
            "project": ["create", "read", "update", "delete"],
            "extra_var": ["create", "read", "update", "delete"],
            "rulebook": ["create", "read", "update", "delete"],
            "decision_environment": ["create", "read", "update", "delete"],
            "credential": ["create", "read", "update", "delete"],
            "event_stream": ["create", "read"],
            "credential_type": ["create", "read"],
            "eda_credential": ["create", "read"],
        },
    },
    {
        "name": "Operator",
        "description": (
            "Has read permissions. "
            "Has permissions to enable and disable rulebook activations."
        ),
        "permissions": {
            "activation": ["read", "enable", "disable", "restart"],
            "activation_instance": ["read"],
            "audit_rule": ["read"],
            "audit_event": ["read"],
            "project": ["read"],
            "extra_var": ["read"],
            "rulebook": ["read"],
            "decision_environment": ["read"],
            "credential": ["read"],
            "event_stream": ["read"],
            "credential_type": ["read"],
            "eda_credential": ["read"],
        },
    },
    {
        "name": "Auditor",
        "description": "Has all read permissions.",
        "permissions": {
            "activation": ["read"],
            "activation_instance": ["read"],
            "audit_rule": ["read"],
            "audit_event": ["read"],
            "user": ["read"],
            "project": ["read"],
            "extra_var": ["read"],
            "rulebook": ["read"],
            "role": ["read"],
            "decision_environment": ["read"],
            "credential": ["read"],
            "event_stream": ["read"],
            "credential_type": ["read"],
            "eda_credential": ["read"],
        },
    },
    {
        "name": "Viewer",
        "description": "Has read permissions, except users and roles.",
        "permissions": {
            "activation": ["read"],
            "activation_instance": ["read"],
            "audit_rule": ["read"],
            "audit_event": ["read"],
            "project": ["read"],
            "extra_var": ["read"],
            "rulebook": ["read"],
            "decision_environment": ["read"],
            "event_stream": ["read"],
            "credential_type": ["read"],
            "eda_credential": ["read"],
        },
    },
]

CREDENTIAL_TYPES = [
    {
        "name": "Source Control",
        "inputs": {
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
        },
        "injectors": {},
        "managed": True,
    },
    {
        "name": "Container Registry",
        "inputs": {
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
                    "help_text": (
                        "A password or token used to authenticate with"
                    ),
                },
                {
                    "id": "verify_ssl",
                    "label": "Verify SSL",
                    "type": "boolean",
                    "default": True,
                },
            ],
            "required": ["host"],
        },
        "injectors": {},
        "managed": True,
    },
    {
        "name": "GPG Public Key",
        "inputs": {
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
        },
        "injectors": {},
        "managed": True,
    },
    {
        "name": "Vault",
        "inputs": {
            "fields": [
                {
                    "id": "vault_id",
                    "label": "Vault Identifier",
                    "type": "string",
                    "help_text": (
                        "Vault identifier to use use with vaulted strings"
                    ),
                },
                {
                    "id": "vault_password",
                    "label": "Vault Password",
                    "type": "string",
                    "secret": True,
                    "help_text": "Vault Password",
                },
            ],
            "required": ["vault_password"],
        },
        "injectors": {},
        "managed": True,
    },
]


class Command(BaseCommand):
    help = "Seed database with initial data."

    @transaction.atomic
    def handle(self, *args, **options):
        self._create_roles()
        self._preload_credential_types()

    def _create_roles(self):
        if models.Role.objects.exists():
            self.stdout.write("Roles already exist. Nothing to do.")
            return

        for role_data in ROLES:
            role = models.Role.objects.create(
                name=role_data["name"], description=role_data["description"]
            )
            total_permissions = 0
            for resource_type, actions in role_data["permissions"].items():
                permissions = list(
                    models.Permission.objects.filter(
                        resource_type=resource_type,
                        action__in=actions,
                    )
                )
                if len(permissions) != len(actions):
                    raise ImproperlyConfigured(
                        f'Permission "{resource_type}" and one of "{actions}" '
                        f"actions is missing in the database."
                    )
                role.permissions.add(*permissions)
                total_permissions += len(actions)
            self.stdout.write(
                'Added role "{0}" with {1} permissions '
                "to {2} resources".format(
                    role_data["name"],
                    total_permissions,
                    len(role_data["permissions"]),
                )
            )
        self.stdout.write(f"Added {len(ROLES)} roles.")

    def _preload_credential_types(self):
        for credential_type_data in CREDENTIAL_TYPES:
            new_type, created = models.CredentialType.objects.get_or_create(
                name=credential_type_data["name"],
                description=credential_type_data.get("description", ""),
                inputs=credential_type_data.get("inputs", {}),
                injectors=credential_type_data.get("injectors", {}),
                managed=credential_type_data.get("managed", True),
            )
            if created:
                self.stdout.write(
                    f"New credential type {new_type.name} is added."
                )
