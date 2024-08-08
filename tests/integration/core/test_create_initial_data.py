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

from aap_eda.core import enums, models
from aap_eda.core.management.commands.create_initial_data import (
    ORG_ROLES,
    Command,
)
from aap_eda.core.utils.credentials import inputs_from_store


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
        else:
            assert f"{obj_name} admin" in role_names
            assert f"{obj_name} use" in role_names


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


def create_old_registry_credential():
    credential = models.Credential.objects.create(
        name="registry cred",
        credential_type=enums.CredentialType.REGISTRY,
        username="fred",
        secret="mysec",
    )
    de = models.DecisionEnvironment.objects.create(
        name="my DE",
        image_url="private-reg.com/fred/de",
        credential=credential,
    )
    return credential, de


def create_old_git_credential():
    credential = models.Credential.objects.create(
        name="git cred",
        credential_type=enums.CredentialType.GITHUB,
        username="fred",
        secret="mysec",
    )
    project = models.Project.objects.create(
        name="my project",
        url="github.com/fred/projects",
        credential=credential,
    )
    return credential, project


@pytest.mark.django_db
def test_copy_registry_credentials(caplog):
    credential, de = create_old_registry_credential()
    Command().handle()

    assert not models.Credential.objects.filter(id=credential.id).exists()
    de.refresh_from_db()
    assert de.eda_credential.name == credential.name
    assert not de.eda_credential.managed
    inputs = inputs_from_store(de.eda_credential.inputs.get_secret_value())
    assert inputs["host"] == "private-reg.com"
    assert inputs["username"] == "fred"
    assert inputs["password"] == "mysec"

    credential.id = None
    credential.save()
    Command().handle()
    assert models.Credential.objects.filter(id=credential.id).exists()


@pytest.mark.django_db
def test_copy_project_credentials(caplog):
    credential, project = create_old_git_credential()
    Command().handle()

    assert not models.Credential.objects.filter(id=credential.id).exists()
    project.refresh_from_db()
    assert project.eda_credential.name == credential.name
    assert not project.eda_credential.managed
    inputs = inputs_from_store(
        project.eda_credential.inputs.get_secret_value()
    )
    assert inputs["username"] == "fred"
    assert inputs["password"] == "mysec"
    credential.id = None
    credential.save()
    Command().handle()
    assert models.Credential.objects.filter(id=credential.id).exists()
