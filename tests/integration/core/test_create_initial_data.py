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

import pytest
from ansible_base.rbac import permission_registry
from ansible_base.rbac.models import DABPermission, RoleDefinition

from aap_eda.core.management.commands.create_initial_data import (
    ORG_ROLES,
    Command,
)


#################################################################
# Roles
#################################################################
@pytest.mark.django_db
def test_create_all_roles():
    assert RoleDefinition.objects.count() == 0
    Command().handle()
    # assert orgs roles are created, e.g. Organization Admin
    created_role_names = [
        rd.name
        for rd in RoleDefinition.objects.filter(
            name__startswith="Organization "
        )
    ]
    assert len(created_role_names) > len(ORG_ROLES)
    for role_data in ORG_ROLES:
        assert role_data["name"] in created_role_names

    # assert object roles are created, e.g. Project Admin, Project Use
    rbac_obj_names = []
    for cls in permission_registry.all_registered_models:
        parent_model = permission_registry.get_parent_model(cls)
        if parent_model and parent_model._meta.model_name == "organization":
            rbac_obj_names.append(cls._meta.verbose_name)
    role_names = []
    for rd in RoleDefinition.objects.all():
        parent_model = permission_registry.get_parent_model(
            rd.content_type.model_class()
        )
        if parent_model and parent_model._meta.model_name == "organization":
            role_names.append(rd.name.lower())
    for obj_name in rbac_obj_names:
        # team model has unique roles
        if obj_name == "team":
            assert "team member" in role_names
            assert "team admin" in role_names
        elif obj_name == "project":
            # Project roles should have EDA prefix
            assert "eda project admin" in role_names
            assert "eda project use" in role_names
        else:
            assert f"{obj_name} admin" in role_names
            assert f"{obj_name} use" in role_names

    # Also check for organization-level project role
    project_org_roles = [
        rd.name.lower()
        for rd in RoleDefinition.objects.filter(
            name__icontains="organization"
        ).filter(name__icontains="project")
    ]
    assert "eda organization project admin" in project_org_roles


@pytest.mark.django_db
def test_add_back_permission():
    assert RoleDefinition.objects.count() == 0
    Command().handle()
    admin_role = RoleDefinition.objects.get(name="Organization Admin")
    perm = admin_role.permissions.last()
    admin_role.permissions.remove(perm)
    assert perm not in admin_role.permissions.all()
    Command().handle()
    assert perm in admin_role.permissions.all()


@pytest.mark.django_db
def test_remove_extra_permission():
    assert RoleDefinition.objects.count() == 0
    Command().handle()
    auditor_role = RoleDefinition.objects.get(name="Organization Auditor")
    perm = DABPermission.objects.filter(codename__startswith="change").first()
    auditor_role.permissions.add(perm)
    assert perm in auditor_role.permissions.all()
    Command().handle()
    assert perm not in auditor_role.permissions.all()
