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
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from ansible_base.rbac.models import RoleDefinition
from ansible_base.rbac import permission_registry

from aap_eda.core.models import DABPermission


CRUD = ["add", "view", "change", "delete"]

# FIXME(cutwater): Role descriptions were taken from the RBAC design document
#  and must be updated.
ROLES = [
    {
        "name": "Admin",
        "description": "Has all permissions",
        "permissions": {
            "activation": [
                "add",
                "view",
                "change",
                "delete",
                "enable",
                "disable",
                "restart",
            ],
            "rulebook_process": ["view", "delete"],
            "audit_rule": ["view"],
            "audit_event": ["view"],
            "organization": ["view", "change", "delete"],
            "team": CRUD + ["member"],
            "project": CRUD,
            "extra_var": CRUD,
            "rulebook": CRUD,
            "decision_environment": CRUD,
            "credential": CRUD,
            "event_stream": ["add", "view"],
        },
    },
    {
        "name": "Editor",
        "description": "Has create and edit permissions.",
        "permissions": {
            "activation": CRUD,
            "rulebook_process": ["view"],
            "audit_rule": ["view"],
            "audit_event": ["view"],
            "organization": ["view"],
            "team": ["view"],
            "project": CRUD,
            "extra_var": CRUD,
            "rulebook": CRUD,
            "decision_environment": CRUD,
            "credential": CRUD,
            "event_stream": ["add", "view"],
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
            "activation": CRUD + ["enable", "disable", "restart"],
            "rulebook_process": ["view", "delete"],
            "audit_rule": ["view"],
            "audit_event": ["view"],
            "organization": ["view"],
            "project": CRUD,
            "extra_var": CRUD,
            "rulebook": CRUD,
            "decision_environment": CRUD,
            "credential": CRUD,
            "event_stream": ["add", "view"],
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
            "audit_event": ["view"],
            "organization": ["view"],
            "project": ["view"],
            "extra_var": ["view"],
            "rulebook": ["view"],
            "decision_environment": ["view"],
            "credential": ["view"],
            "event_stream": ["view"],
        },
    },
    {
        "name": "Auditor",
        "description": "Has all read permissions.",
        "permissions": {
            "activation": ["view"],
            "rulebook_process": ["view"],
            "audit_rule": ["view"],
            "audit_event": ["view"],
            "organization": ["view"],
            "team": ["view"],
            "project": ["view"],
            "extra_var": ["view"],
            "rulebook": ["view"],
            "decision_environment": ["view"],
            "credential": ["view"],
            "event_stream": ["view"],
        },
    },
    {
        "name": "Viewer",
        "description": "Has read permissions, except users and roles.",
        "permissions": {
            "activation": ["view"],
            "rulebook_process": ["view"],
            "audit_rule": ["view"],
            "audit_event": ["view"],
            "organization": ["view"],
            "team": ["view"],
            "project": ["view"],
            "extra_var": ["view"],
            "rulebook": ["view"],
            "decision_environment": ["view"],
            "event_stream": ["view"],
        },
    },
]


class Command(BaseCommand):
    help = "Seed database with initial roles."

    @transaction.atomic
    def handle(self, *args, **options):
        self._create_org_roles()
        self._create_obj_roles()

    def _create_org_roles(self):
        org_ct = ContentType.objects.get(model='organization')
        for role_data in ROLES:
            role, _ = RoleDefinition.objects.get_or_create(
                name=role_data["name"], description=role_data["description"],
                content_type=org_ct, managed=True
            )
            permissions = []
            for resource_type, actions in role_data["permissions"].items():
                model_permissions = list(
                    DABPermission.objects.filter(
                        codename__in=[f'{action}_{resource_type.replace("_", "")}' for action in actions],
                    )
                )
                if len(model_permissions) != len(actions):
                    raise ImproperlyConfigured(
                        f'Permission "{resource_type}" and one of "{actions}" '
                        f"actions is missing in the database, found {[p.codename for p in model_permissions]}."
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
        self.stdout.write(f"Added {len(ROLES)} roles.")

    def _create_obj_roles(self):
        org_ct = ContentType.objects.get(model='organization')
        if RoleDefinition.objects.exclude(content_type__in=[org_ct, None]).exists():
            self.stdout.write("Organization roles already exist. Not creating.")
            return

        for cls in permission_registry.all_registered_models:
            ct = ContentType.objects.get_for_model(cls)
            if ct._meta.model_name == 'organization':
                continue  # covered by org roles
            permissions = list(DABPermission.objects.filter(content_type=ct))
            role = RoleDefinition.objects.create(
                name=f'{cls._meta.verbose_name.title()} Admin',
                description=f'Has all permissions to a single {cls._meta.verbose_name}',
                content_type=ct, managed=True
            )
            role.permissions.set(permissions)
            self.stdout.write(
                f'Added role {role.name} with {len(permissions)} permissions to itself'
            )
