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
import logging
from urllib.parse import urlparse

from ansible_base.rbac import permission_registry
from ansible_base.rbac.models import DABPermission, RoleDefinition
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.core.management import BaseCommand
from django.db import transaction

from aap_eda.core import enums, models
from aap_eda.core.tasking import enable_redis_prefix
from aap_eda.core.utils.credentials import inputs_to_store

CRUD = ["add", "view", "change", "delete"]
LOGGER = logging.getLogger(__name__)

# FIXME(cutwater): Role descriptions were taken from the RBAC design document
#  and must be updated.
ORG_ROLES = [
    {
        "name": "Admin",
        "description": "Has all permissions",
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
        "name": "Editor",
        "description": "Has create and edit permissions.",
        "permissions": {
            "activation": ["add", "view", "delete"],
            "rulebook_process": ["view"],
            "audit_rule": ["view"],
            "organization": ["view"],
            "team": ["view"],
            "project": CRUD + ["sync"],
            "rulebook": ["view"],
            "decision_environment": CRUD,
            "eda_credential": ["add", "view"],
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
                "add",
                "view",
                "delete",
                "enable",
                "disable",
                "restart",
            ],
            "rulebook_process": ["view"],
            "audit_rule": ["view"],
            "organization": ["view"],
            "project": CRUD + ["sync"],
            "rulebook": ["view"],
            "decision_environment": CRUD,
            "eda_credential": ["add", "view"],
        },
    },
    {
        "name": "Operator",
        "description": (
            "Has read permissions. "
            "Has permissions to enable and disable rulebook activations."
        ),
        "permissions": {
            "activation": ["view", "enable", "disable", "restart"],
            "rulebook_process": ["view"],
            "audit_rule": ["view"],
            "organization": ["view"],
            "project": ["view"],
            "rulebook": ["view"],
            "decision_environment": ["view"],
            "eda_credential": ["view"],
        },
    },
    {
        "name": "Auditor",
        "description": "Has all read permissions.",
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
        },
    },
    {
        "name": "Viewer",
        "description": "Has read permissions, except users and roles.",
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
]


def populate_credential_types(
    credential_types: list[dict],
) -> list[models.CredentialType]:
    created_credential_types = []

    for credential_type_data in credential_types:
        new_type, created = models.CredentialType.objects.get_or_create(
            name=credential_type_data["name"],
            description=credential_type_data.get("description", ""),
            namespace=credential_type_data.get("namespace"),
            kind=credential_type_data.get("kind", "cloud"),
            inputs=credential_type_data.get("inputs", {}),
            injectors=credential_type_data.get("injectors", {}),
            managed=credential_type_data.get("managed", True),
        )
        if created:
            created_credential_types.append(new_type)

    return created_credential_types


class Command(BaseCommand):
    help = "Seed database with initial data."

    @transaction.atomic
    def handle(self, *args, **options):
        self._preload_credential_types()
        self._copy_registry_credentials()
        self._copy_scm_credentials()
        self._create_org_roles()
        self._create_obj_roles()
        enable_redis_prefix()

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
        for role_data in ORG_ROLES:
            role, _ = RoleDefinition.objects.get_or_create(
                name=role_data["name"],
                defaults={
                    "description": role_data["description"],
                    "content_type": org_ct,
                    "managed": True,
                },
            )
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
                        f'Permission "{resource_type}" and one of "{actions}" '
                        "actions is missing in the database, "
                        f"found {[p.codename for p in model_permissions]}."
                    )
                permissions.extend(model_permissions)
            role.permissions.set(permissions)
            self.stdout.write(
                'Added role "{0}" with {1} permissions '
                "to {2} resources".format(
                    role_data["name"],
                    len(permissions),
                    len(role_data["permissions"]),
                )
            )
        self.stdout.write(f"Added {len(ORG_ROLES)} roles.")

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
            role, created = RoleDefinition.objects.get_or_create(
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

            # Special case to create team member role
            if cls._meta.model_name == "team":
                member_permissions = [
                    p
                    for p in permissions
                    if p.codename in ("view_team", "member_team")
                ]
                desc = "Inherits permissions assigned to this team"
                role, created = RoleDefinition.objects.get_or_create(
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
                        f"Added role {role.name} with {len(permissions)} "
                        "permissions to itself"
                    )
