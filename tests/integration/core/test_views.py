import pytest
from rest_framework import status
from rest_framework.test import APIClient


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
    response = client.get("/status/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"status": "OK"}
