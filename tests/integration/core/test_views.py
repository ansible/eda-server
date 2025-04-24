import pytest
from ansible_base.lib.constants import STATUS_GOOD
from rest_framework import status
from rest_framework.test import APIClient

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
    response = client.get(f"{api_url_v1}/status/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"status": STATUS_GOOD}
