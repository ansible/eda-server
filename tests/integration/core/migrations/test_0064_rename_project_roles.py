#  Copyright 2025 Red Hat, Inc.
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
from django.apps import apps
from django.core.management import call_command


@pytest.fixture
def rollback_migration():
    """Rollback to the previous migration and restore after test."""
    call_command("migrate", "core", "0063")
    yield
    call_command("migrate")


@pytest.mark.django_db
def test_rename_project_roles_forward_and_reverse(rollback_migration):
    """Test that roles are renamed correctly and can be reverted."""
    RoleDefinition = apps.get_model("dab_rbac", "RoleDefinition")  # noqa: N806

    # Create initial roles
    RoleDefinition.objects.create(name="Project Admin")
    RoleDefinition.objects.create(name="Project Use")
    RoleDefinition.objects.create(name="Organization Project Admin")

    # Apply the migration
    call_command("migrate", "core", "0064")

    # Check that roles were renamed
    assert RoleDefinition.objects.filter(name="EDA Project Admin").exists()
    assert not RoleDefinition.objects.filter(name="Project Admin").exists()
    assert RoleDefinition.objects.filter(name="EDA Project Use").exists()
    assert not RoleDefinition.objects.filter(name="Project Use").exists()
    assert RoleDefinition.objects.filter(
        name="EDA Organization Project Admin"
    ).exists()
    assert not RoleDefinition.objects.filter(
        name="Organization Project Admin"
    ).exists()

    # Rollback the migration
    call_command("migrate", "core", "0063")

    # Check that roles were reverted
    assert RoleDefinition.objects.filter(name="Project Admin").exists()
    assert RoleDefinition.objects.filter(name="Project Use").exists()
    assert RoleDefinition.objects.filter(
        name="Organization Project Admin"
    ).exists()
    assert not RoleDefinition.objects.filter(name="EDA Project Admin").exists()
    assert not RoleDefinition.objects.filter(name="EDA Project Use").exists()
    assert not RoleDefinition.objects.filter(
        name="EDA Organization Project Admin"
    ).exists()


@pytest.mark.django_db
def test_rename_project_roles_target_exists(rollback_migration):
    """Test that renaming is skipped when target role already exists."""
    RoleDefinition = apps.get_model("dab_rbac", "RoleDefinition")  # noqa: N806

    # Create both original and target roles
    RoleDefinition.objects.create(name="Project Admin")
    RoleDefinition.objects.create(name="EDA Project Admin")

    # Apply the migration
    call_command("migrate", "core", "0064")

    # Both should exist, original not renamed due to target already existing
    assert RoleDefinition.objects.filter(name="Project Admin").exists()
    assert RoleDefinition.objects.filter(name="EDA Project Admin").exists()


@pytest.mark.django_db
def test_rename_project_roles_missing_roles(rollback_migration):
    """Test that migration handles missing roles gracefully."""
    RoleDefinition = apps.get_model("dab_rbac", "RoleDefinition")  # noqa: N806

    # Only create one role
    RoleDefinition.objects.create(name="Project Admin")
    # Other roles are missing

    # Apply the migration
    call_command("migrate", "core", "0064")

    # Only existing roles should be renamed
    assert RoleDefinition.objects.filter(name="EDA Project Admin").exists()
    assert not RoleDefinition.objects.filter(name="Project Admin").exists()
    # Missing roles should not cause errors and should not exist
    assert not RoleDefinition.objects.filter(name="EDA Project Use").exists()
    assert not RoleDefinition.objects.filter(
        name="EDA Organization Project Admin"
    ).exists()
