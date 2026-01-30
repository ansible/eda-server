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

"""Unit tests for Project serializers with sync configuration."""

from datetime import timedelta

import pytest
from django.utils import timezone

from aap_eda.api.serializers.project import ProjectRefSerializer
from aap_eda.core import models


@pytest.mark.django_db
class TestProjectRefSerializerNeedsUpdate:
    """Test ProjectRefSerializer includes needs_update_on_launch field."""

    def test_includes_needs_update_on_launch_field(self, default_organization):
        """Test that serializer includes needs_update_on_launch in output."""
        project = models.Project.objects.create(
            name="test-project",
            url="https://github.com/example/repo",
            scm_update_on_launch=True,
            scm_update_cache_timeout=0,
            organization=default_organization,
            git_hash="abc123",
        )

        serializer = ProjectRefSerializer(project)
        data = serializer.data

        assert "needs_update_on_launch" in data
        assert data["needs_update_on_launch"] is True

    def test_needs_update_false_when_disabled(self, default_organization):
        """Test property is False when update on launch is disabled."""
        project = models.Project.objects.create(
            name="test-project",
            url="https://github.com/example/repo",
            scm_update_on_launch=False,
            scm_update_cache_timeout=300,
            organization=default_organization,
            git_hash="abc123",
        )

        serializer = ProjectRefSerializer(project)
        data = serializer.data

        assert data["needs_update_on_launch"] is False

    def test_needs_update_true_when_cache_expired(self, default_organization):
        """Test property is True when cache has expired."""
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

        serializer = ProjectRefSerializer(project)
        data = serializer.data

        assert data["needs_update_on_launch"] is True

    def test_needs_update_false_when_cache_valid(self, default_organization):
        """Test property is False when cache is still valid."""
        project = models.Project.objects.create(
            name="test-project",
            url="https://github.com/example/repo",
            scm_update_on_launch=True,
            scm_update_cache_timeout=300,
            organization=default_organization,
            git_hash="abc123",
        )

        # Mock last_synced_at to 1 minute ago (cache still valid)
        recent_time = timezone.now() - timedelta(seconds=60)
        models.Project.objects.filter(pk=project.pk).update(
            last_synced_at=recent_time
        )
        project.refresh_from_db()

        serializer = ProjectRefSerializer(project)
        data = serializer.data

        assert data["needs_update_on_launch"] is False
