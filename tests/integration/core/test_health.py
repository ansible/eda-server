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

from unittest.mock import patch

import pytest

from aap_eda.core.health import check_dispatcherd_workers_health


@pytest.mark.django_db
def test_check_dispatcherd_workers_health_all_healthy():
    """Test check_dispatcherd_workers_health when both project and rulebook
    workers are healthy."""
    with patch(
        "aap_eda.core.health.check_default_worker_health", return_value=True
    ), patch(
        "aap_eda.core.health.check_rulebook_queue_health", return_value=True
    ), patch(
        "aap_eda.core.health.settings.RULEBOOK_WORKER_QUEUES", ["activation"]
    ):
        assert check_dispatcherd_workers_health() is True


@pytest.mark.django_db
def test_check_dispatcherd_workers_health_project_workers_unhealthy():
    """Test check_dispatcherd_workers_health when project workers are
    unhealthy."""
    with patch(
        "aap_eda.core.health.check_default_worker_health", return_value=False
    ):
        assert check_dispatcherd_workers_health() is False


@pytest.mark.django_db
def test_check_dispatcherd_workers_health_rulebook_workers_unhealthy():
    """Test check_dispatcherd_workers_health when rulebook workers are
    unhealthy."""
    with patch(
        "aap_eda.core.health.check_default_worker_health", return_value=True
    ), patch(
        "aap_eda.core.health.check_rulebook_queue_health", return_value=False
    ), patch(
        "aap_eda.core.health.settings.RULEBOOK_WORKER_QUEUES", ["activation"]
    ):
        assert check_dispatcherd_workers_health() is False


@pytest.mark.django_db
def test_check_dispatcherd_workers_health_no_rulebook_queues():
    """Test check_dispatcherd_workers_health when no rulebook queues are
    configured."""
    with patch(
        "aap_eda.core.health.check_default_worker_health", return_value=True
    ), patch("aap_eda.core.health.settings.RULEBOOK_WORKER_QUEUES", []):
        assert check_dispatcherd_workers_health() is True


@pytest.mark.django_db
def test_check_dispatcherd_workers_health_multiple_queues():
    """Test check_dispatcherd_workers_health with multiple rulebook queues
    (checks first)."""
    with patch(
        "aap_eda.core.health.check_default_worker_health", return_value=True
    ), patch(
        "aap_eda.core.health.check_rulebook_queue_health", return_value=True
    ) as mock_check_queue, patch(
        "aap_eda.core.health.settings.RULEBOOK_WORKER_QUEUES",
        ["activation", "secondary", "tertiary"],
    ):
        result = check_dispatcherd_workers_health()
        assert result is True
        # Verify only first queue was checked
        mock_check_queue.assert_called_once_with("activation")


@pytest.mark.django_db
def test_check_dispatcherd_workers_health_exception_handling():
    """Test check_dispatcherd_workers_health handles exceptions gracefully."""
    with patch(
        "aap_eda.core.health.check_default_worker_health",
        side_effect=Exception("Unexpected error"),
    ):
        assert check_dispatcherd_workers_health() is False


@pytest.mark.django_db
def test_check_dispatcherd_workers_health_project_exception():
    """Test check_dispatcherd_workers_health when project queue check raises
    exception."""
    with patch(
        "aap_eda.core.health.check_default_worker_health",
        side_effect=ConnectionError("Dispatcherd connection failed"),
    ):
        assert check_dispatcherd_workers_health() is False


@pytest.mark.django_db
def test_check_dispatcherd_workers_health_rulebook_exception():
    """Test check_dispatcherd_workers_health when rulebook queue check raises
    exception."""
    with patch(
        "aap_eda.core.health.check_default_worker_health", return_value=True
    ), patch(
        "aap_eda.core.health.check_rulebook_queue_health",
        side_effect=RuntimeError("Queue inspection failed"),
    ), patch(
        "aap_eda.core.health.settings.RULEBOOK_WORKER_QUEUES", ["activation"]
    ):
        assert check_dispatcherd_workers_health() is False


@pytest.mark.django_db
def test_check_dispatcherd_workers_health_settings_exception():
    """Test check_dispatcherd_workers_health when accessing settings raises
    exception."""
    with patch(
        "aap_eda.core.health.check_default_worker_health", return_value=True
    ), patch(
        "aap_eda.core.health.getattr",
        side_effect=AttributeError("Settings not available"),
    ):
        assert check_dispatcherd_workers_health() is False
