import pytest
from ansible_base.rbac.models import RoleDefinition

from aap_eda.core.management.commands.create_initial_data import Command
from aap_eda.core.models import DABPermission


@pytest.mark.django_db
def test_create_all_roles():
    assert RoleDefinition.objects.count() == 0
    Command().handle()
    role_types = [
        rd.content_type.model if rd.content_type else None
        for rd in RoleDefinition.objects.all()
    ]
    assert "organization" in role_types
    assert "credential" in role_types


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
