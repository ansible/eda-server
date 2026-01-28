from unittest.mock import patch

import pytest
from ansible_base.lib.constants import STATUS_FAILED, STATUS_GOOD
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core.views import StatusView
from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_healthz_view():
    client = APIClient()
    client.force_authenticate(user=None)
    response = client.get("/_healthz")
    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"status": "OK"}


@pytest.mark.django_db
def test_status_view():
    client = APIClient()
    client.force_authenticate(user=None)
    with patch(
        "aap_eda.core.views.StatusView._check_dispatcherd", return_value=True
    ):
        response = client.get(f"{api_url_v1}/status/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"status": STATUS_GOOD}


@pytest.mark.django_db
def test_status_view_database_failure():
    client = APIClient()
    client.force_authenticate(user=None)
    with patch(
        "aap_eda.core.views.StatusView._check_database", return_value=False
    ), patch(
        "aap_eda.core.views.StatusView._check_dispatcherd", return_value=True
    ):
        response = client.get(f"{api_url_v1}/status/")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data == {
            "status": STATUS_FAILED,
            "message": "Database connection failed",
        }


@pytest.mark.django_db
def test_status_view_dispatcherd_failure():
    """Test status view when dispatcherd workers are unavailable."""
    client = APIClient()
    client.force_authenticate(user=None)
    with patch(
        "aap_eda.core.views.StatusView._check_dispatcherd", return_value=False
    ):
        response = client.get(f"{api_url_v1}/status/")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data == {
            "status": STATUS_FAILED,
            "message": "Dispatcherd workers unavailable",
        }


@pytest.mark.django_db
def test_status_view_multiple_failures():
    """Test status view when both database and dispatcherd fail."""
    client = APIClient()
    client.force_authenticate(user=None)
    with patch(
        "aap_eda.core.views.StatusView._check_database", return_value=False
    ), patch(
        "aap_eda.core.views.StatusView._check_dispatcherd", return_value=False
    ):
        response = client.get(f"{api_url_v1}/status/")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data == {
            "status": STATUS_FAILED,
            "message": "Database connection failed; "
            "Dispatcherd workers unavailable",
        }


@pytest.mark.django_db
def test_check_dispatcherd_project_workers_healthy():
    """Test _check_dispatcherd when project workers are healthy."""
    with patch(
        "aap_eda.core.views.check_project_queue_health", return_value=True
    ), patch(
        "aap_eda.core.views.check_rulebook_queue_health", return_value=True
    ), patch(
        "aap_eda.core.views.settings.RULEBOOK_WORKER_QUEUES", ["activation"]
    ):
        assert StatusView._check_dispatcherd() is True


@pytest.mark.django_db
def test_check_dispatcherd_project_workers_unhealthy():
    """Test _check_dispatcherd when project workers are unhealthy."""
    with patch(
        "aap_eda.core.views.check_project_queue_health", return_value=False
    ):
        assert StatusView._check_dispatcherd() is False


@pytest.mark.django_db
def test_check_dispatcherd_activation_workers_unhealthy():
    """Test _check_dispatcherd when activation workers are unhealthy."""
    with patch(
        "aap_eda.core.views.check_project_queue_health", return_value=True
    ), patch(
        "aap_eda.core.views.check_rulebook_queue_health", return_value=False
    ), patch(
        "aap_eda.core.views.settings.RULEBOOK_WORKER_QUEUES", ["activation"]
    ):
        assert StatusView._check_dispatcherd() is False


@pytest.mark.django_db
def test_check_dispatcherd_no_rulebook_queues():
    """Test _check_dispatcherd when no rulebook queues are configured."""
    with patch(
        "aap_eda.core.views.check_project_queue_health", return_value=True
    ), patch("aap_eda.core.views.settings.RULEBOOK_WORKER_QUEUES", []):
        assert StatusView._check_dispatcherd() is True


@pytest.mark.django_db
def test_check_dispatcherd_exception_handling():
    """Test _check_dispatcherd handles exceptions gracefully."""
    with patch(
        "aap_eda.core.views.check_project_queue_health",
        side_effect=Exception("Unexpected error"),
    ):
        assert StatusView._check_dispatcherd() is False


@pytest.mark.django_db
def test_check_dispatcherd_multiple_queues():
    """Test _check_dispatcherd with multiple rulebook queues (checks first)."""
    with patch(
        "aap_eda.core.views.check_project_queue_health", return_value=True
    ), patch(
        "aap_eda.core.views.check_rulebook_queue_health", return_value=True
    ) as mock_check_queue, patch(
        "aap_eda.core.views.settings.RULEBOOK_WORKER_QUEUES",
        ["activation", "secondary", "tertiary"],
    ):
        result = StatusView._check_dispatcherd()
        assert result is True
        # Verify only first queue was checked
        mock_check_queue.assert_called_once_with("activation")
