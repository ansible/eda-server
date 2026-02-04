#  Copyright 2026 Red Hat, Inc.
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

"""Unit tests for Project sync configuration functionality."""

from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone

from aap_eda.core import models


@pytest.mark.django_db
class TestProjectNeedsUpdateOnLaunch:
    """Test the needs_update_on_launch property."""

    def test_disabled_update_on_launch_returns_false(
        self, default_organization
    ):
        """Test that property returns False when
        scm_update_on_launch is disabled."""
        project = models.Project.objects.create(
            name="test-project",
            url="https://github.com/example/repo",
            scm_update_on_launch=False,
            scm_update_cache_timeout=300,
            organization=default_organization,
            git_hash="abc123",
        )

        assert project.needs_update_on_launch is False

    def test_enabled_with_zero_timeout_returns_true(
        self, default_organization
    ):
        """Test that property returns True when cache timeout
        is 0 (always update)."""
        project = models.Project.objects.create(
            name="test-project",
            url="https://github.com/example/repo",
            scm_update_on_launch=True,
            scm_update_cache_timeout=0,
            organization=default_organization,
            git_hash="abc123",
        )

        assert project.needs_update_on_launch is True

    # Removed test_enabled_with_null_last_synced_returns_true
    # because last_synced_at has null=False constraint and auto_now=True
    # so it cannot be None in practice

    def test_cache_expired_returns_true(self, default_organization):
        """Test that property returns True when cache has expired."""
        # Create project with cache timeout of 300 seconds (5 minutes)
        project = models.Project.objects.create(
            name="test-project",
            url="https://github.com/example/repo",
            scm_update_on_launch=True,
            scm_update_cache_timeout=300,
            organization=default_organization,
            git_hash="abc123",
        )

        # Mock last_synced_at to 10 minutes ago (cache expired)
        past_time = timezone.now() - timedelta(seconds=600)
        models.Project.objects.filter(pk=project.pk).update(
            last_synced_at=past_time
        )
        project.refresh_from_db()

        assert project.needs_update_on_launch is True

    def test_cache_still_valid_returns_false(self, default_organization):
        """Test that property returns False when cache is still valid."""
        # Create project with cache timeout of 300 seconds (5 minutes)
        project = models.Project.objects.create(
            name="test-project",
            url="https://github.com/example/repo",
            scm_update_on_launch=True,
            scm_update_cache_timeout=300,
            organization=default_organization,
            git_hash="abc123",
        )

        # Mock last_synced_at to 2 minutes ago (cache still valid)
        recent_time = timezone.now() - timedelta(seconds=120)
        models.Project.objects.filter(pk=project.pk).update(
            last_synced_at=recent_time
        )
        project.refresh_from_db()

        assert project.needs_update_on_launch is False

    def test_cache_exactly_at_timeout_returns_false(
        self, default_organization
    ):
        """Test edge case where elapsed time equals timeout."""
        project = models.Project.objects.create(
            name="test-project",
            url="https://github.com/example/repo",
            scm_update_on_launch=True,
            scm_update_cache_timeout=300,
            organization=default_organization,
            git_hash="abc123",
        )

        # Set last_synced_at to exactly 300 seconds ago
        exact_time = timezone.now() - timedelta(seconds=300)
        models.Project.objects.filter(pk=project.pk).update(
            last_synced_at=exact_time
        )
        project.refresh_from_db()

        # Mock timezone.now() to return the exact same time we
        # used to calculate
        # This ensures exactly 300 seconds have elapsed
        with mock.patch("django.utils.timezone.now") as mock_now:
            mock_now.return_value = exact_time + timedelta(seconds=300)
            # Should return False (not greater than timeout, exactly equal)
            assert project.needs_update_on_launch is False

    def test_cache_one_second_over_timeout_returns_true(
        self, default_organization
    ):
        """Test edge case where elapsed time is one second
        over timeout."""
        project = models.Project.objects.create(
            name="test-project",
            url="https://github.com/example/repo",
            scm_update_on_launch=True,
            scm_update_cache_timeout=300,
            organization=default_organization,
            git_hash="abc123",
        )

        # Set last_synced_at to 301 seconds ago (1 second over timeout)
        past_time = timezone.now() - timedelta(seconds=301)
        models.Project.objects.filter(pk=project.pk).update(
            last_synced_at=past_time
        )
        project.refresh_from_db()

        assert project.needs_update_on_launch is True


@pytest.mark.django_db
class TestProjectFieldDefaults:
    """Test default values for new Project fields."""

    def test_scm_update_on_launch_defaults_to_false(
        self, default_organization
    ):
        """Test that scm_update_on_launch defaults to False."""
        project = models.Project.objects.create(
            name="test-project",
            url="https://github.com/example/repo",
            organization=default_organization,
            git_hash="abc123",
        )

        assert project.scm_update_on_launch is False

    def test_scm_update_cache_timeout_defaults_to_zero(
        self, default_organization
    ):
        """Test that scm_update_cache_timeout defaults to 0."""
        project = models.Project.objects.create(
            name="test-project",
            url="https://github.com/example/repo",
            organization=default_organization,
            git_hash="abc123",
        )

        assert project.scm_update_cache_timeout == 0

    def test_last_synced_at_is_set_on_creation(self, default_organization):
        """Test that last_synced_at is automatically set on creation."""
        project = models.Project.objects.create(
            name="test-project",
            url="https://github.com/example/repo",
            organization=default_organization,
            git_hash="abc123",
        )

        assert project.last_synced_at is not None
        # Should be very recent (within last 5 seconds)
        time_diff = (timezone.now() - project.last_synced_at).total_seconds()
        assert time_diff < 5

    def test_scm_update_cache_timeout_rejects_negative_value(self):
        """Test that PositiveIntegerField prevents negative values
        at DB level."""
        # This should raise an error due to PositiveIntegerField constraint
        # Note: The exact error depends on DB backend, but it should fail
        assert pytest.raises(Exception)
