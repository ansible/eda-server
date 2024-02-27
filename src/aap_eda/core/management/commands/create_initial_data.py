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
from ansible_base.rbac import permission_registry
from ansible_base.rbac.models import RoleDefinition
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.core.management import BaseCommand
from django.db import transaction

from aap_eda.core.models import DABPermission

CRUD = ["add", "view", "change", "delete"]

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
                "change",
                "delete",
                "enable",
                "disable",
                "restart",
            ],
            "rulebook_process": ["view", "delete"],
            "audit_rule": ["view"],
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
            "activation": CRUD,
            "rulebook_process": ["view"],
            "audit_rule": ["view"],
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
    parent_child_models = {
        "project": "rulebook",
        "activation": "rulebookprocess",
        "activationinstance": "auditrule",
    }

    @transaction.atomic
    def handle(self, *args, **options):
        self._create_org_roles()
        self._create_obj_roles()

    def _create_org_roles(self):
        org_ct = ContentType.objects.get(model="organization")
        for role_data in ORG_ROLES:
            role, _ = RoleDefinition.objects.get_or_create(
                name=role_data["name"],
                description=role_data["description"],
                content_type=org_ct,
                managed=True,
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
            model_name = cls._meta.model_name
            # ignore if the model is organization, covered by org roles
            # or child model, inherits permissions from parent model
            if (
                model_name == "organization"
                or model_name in self.parent_child_models.values()
            ):
                continue
            permissions = self._create_permissions_for_content_type(ct)
            desc = f"Has all permissions to a single {cls._meta.verbose_name}"
            # parent model should add permissions related to its child models
            if model_name in self.parent_child_models.keys():
                child_model = permission_registry._name_to_model[
                    self.parent_child_models[model_name]
                ]
                child_ct = ContentType.objects.get_for_model(child_model)
                permissions.extend(
                    self._create_permissions_for_content_type(child_ct)
                )
                desc += f" and its child resources - {child_model._meta.verbose_name}"  # noqa: E501
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
