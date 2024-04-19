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
from ansible_base.rbac.models import DABPermission, RoleDefinition

from aap_eda.core.management.commands.create_initial_data import Command


@pytest.mark.django_db
def test_create_all_roles():
    assert RoleDefinition.objects.count() == 0
    Command().handle()
    role_types = [
        rd.content_type.model if rd.content_type else None
        for rd in RoleDefinition.objects.all()
    ]
    assert "organization" in role_types
    assert "edacredential" in role_types


@pytest.mark.django_db
def test_add_back_permission():
    assert RoleDefinition.objects.count() == 0
    Command().handle()
    admin_role = RoleDefinition.objects.get(name="Admin")
    perm = admin_role.permissions.last()
    admin_role.permissions.remove(perm)
    assert perm not in admin_role.permissions.all()
    Command().handle()
    assert perm in admin_role.permissions.all()


@pytest.mark.django_db
def test_remove_extra_permission():
    assert RoleDefinition.objects.count() == 0
    Command().handle()
    auditor_role = RoleDefinition.objects.get(name="Auditor")
    perm = DABPermission.objects.filter(codename__startswith="change").first()
    auditor_role.permissions.add(perm)
    assert perm in auditor_role.permissions.all()
    Command().handle()
    assert perm not in auditor_role.permissions.all()
