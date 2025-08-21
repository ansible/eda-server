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
from io import StringIO

import pytest
from django.core.management import base, call_command

from aap_eda.core import models


@pytest.mark.django_db
def test_fix_project_state_successful(default_organization):
    """Test successfully updating project state."""
    # Create a test project
    project = models.Project.objects.create(
        name="test-project",
        description="Test Project",
        url="https://git.example.com/test/project",
        git_hash="abc123",
        organization=default_organization,
        import_state=models.Project.ImportState.PENDING,
        import_error="Old error message",
    )

    out = StringIO()
    call_command(
        "fix_project_state",
        "--name",
        "test-project",
        "--state",
        "completed",
        "--error",
        "New error message",
        stdout=out,
    )

    project.refresh_from_db()
    output = out.getvalue()

    assert project.import_state == models.Project.ImportState.COMPLETED
    assert project.import_error == "New error message"
    assert "Successfully updated project 'test-project'" in output
    assert "Import state: pending -> completed" in output
    assert "Import error: Old error message -> New error message" in output


@pytest.mark.django_db
def test_fix_project_state_without_error(default_organization):
    """Test updating project state without changing error message."""
    project = models.Project.objects.create(
        name="test-project-2",
        description="Test Project 2",
        url="https://git.example.com/test/project2",
        git_hash="def456",
        organization=default_organization,
        import_state=models.Project.ImportState.PENDING,
        import_error="Existing error",
    )

    out = StringIO()
    call_command(
        "fix_project_state",
        "--name",
        "test-project-2",
        "--state",
        "failed",
        stdout=out,
    )

    project.refresh_from_db()
    output = out.getvalue()

    assert project.import_state == models.Project.ImportState.FAILED
    assert project.import_error == "Existing error"  # Should remain unchanged
    assert "Successfully updated project 'test-project-2'" in output
    assert "Import state: pending -> failed" in output
    assert "Import error: Existing error -> (unchanged)" in output


@pytest.mark.django_db
def test_fix_project_state_completed_clears_error(default_organization):
    """Test that setting state to completed without providing error clears
    existing error."""
    project = models.Project.objects.create(
        name="test-project-clear",
        description="Test Project Clear Error",
        url="https://git.example.com/test/project-clear",
        git_hash="ghi789",
        organization=default_organization,
        import_state=models.Project.ImportState.FAILED,
        import_error="Previous import error",
    )

    out = StringIO()
    call_command(
        "fix_project_state",
        "--name",
        "test-project-clear",
        "--state",
        "completed",
        stdout=out,
    )

    project.refresh_from_db()
    output = out.getvalue()

    assert project.import_state == models.Project.ImportState.COMPLETED
    assert project.import_error is None  # Should be cleared
    assert "Successfully updated project 'test-project-clear'" in output
    assert "Import state: failed -> completed" in output
    assert "Import error: Previous import error -> (cleared)" in output


@pytest.mark.django_db
def test_fix_project_state_completed_with_explicit_error(default_organization):
    """Test that setting state to completed with explicit error keeps the
    provided error."""
    project = models.Project.objects.create(
        name="test-project-explicit",
        description="Test Project Explicit Error",
        url="https://git.example.com/test/project-explicit",
        git_hash="jkl012",
        organization=default_organization,
        import_state=models.Project.ImportState.FAILED,
        import_error="Previous import error",
    )

    out = StringIO()
    call_command(
        "fix_project_state",
        "--name",
        "test-project-explicit",
        "--state",
        "completed",
        "--error",
        "Custom completion message",
        stdout=out,
    )

    project.refresh_from_db()
    output = out.getvalue()

    assert project.import_state == models.Project.ImportState.COMPLETED
    assert (
        project.import_error == "Custom completion message"
    )  # Should use provided error
    assert "Successfully updated project 'test-project-explicit'" in output
    assert "Import state: failed -> completed" in output
    assert (
        "Import error: Previous import error -> Custom completion message"
        in output
    )


@pytest.mark.django_db
def test_fix_project_state_failed_preserves_error(default_organization):
    """Test that setting state to failed without providing error preserves
    existing error."""
    project = models.Project.objects.create(
        name="test-project-preserve",
        description="Test Project Preserve Error",
        url="https://git.example.com/test/project-preserve",
        git_hash="mno345",
        organization=default_organization,
        import_state=models.Project.ImportState.RUNNING,
        import_error="Existing error message",
    )

    out = StringIO()
    call_command(
        "fix_project_state",
        "--name",
        "test-project-preserve",
        "--state",
        "failed",
        stdout=out,
    )

    project.refresh_from_db()
    output = out.getvalue()

    assert project.import_state == models.Project.ImportState.FAILED
    assert (
        project.import_error == "Existing error message"
    )  # Should remain unchanged
    assert "Successfully updated project 'test-project-preserve'" in output
    assert "Import state: running -> failed" in output
    assert "Import error: Existing error message -> (unchanged)" in output


@pytest.mark.django_db
def test_fix_project_state_nonexistent_project():
    """Test command with non-existent project."""
    out = StringIO()

    with pytest.raises(base.CommandError) as exc_info:
        call_command(
            "fix_project_state",
            "--name",
            "nonexistent-project",
            "--state",
            "completed",
            stdout=out,
        )

    assert "Project 'nonexistent-project' does not exist." in str(
        exc_info.value
    )


@pytest.mark.parametrize(
    "invalid_state", ["invalid-state", "pending", "running"]
)
@pytest.mark.django_db
def test_fix_project_state_invalid_states(invalid_state):
    """Test command rejects invalid import states."""
    out = StringIO()

    with pytest.raises(base.CommandError) as exc_info:
        call_command(
            "fix_project_state",
            "--name",
            "test-project",
            "--state",
            invalid_state,
            stdout=out,
        )

    error_msg = str(exc_info.value)
    # Handle both quoted and unquoted error message formats
    assert (
        f"invalid choice: '{invalid_state}'" in error_msg
        or f"invalid choice: {invalid_state}" in error_msg
    )
    assert "choose from" in error_msg
    assert "failed" in error_msg
    assert "completed" in error_msg


@pytest.mark.django_db
def test_fix_project_state_missing_required_args():
    """Test command with missing required arguments."""
    out = StringIO()

    with pytest.raises(base.CommandError) as exc_info:
        call_command("fix_project_state", stdout=out)

    assert (
        "the following arguments are required: -n/--name, -s/--state"
        in str(exc_info.value)
    )
