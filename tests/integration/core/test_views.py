from rest_framework import status
from rest_framework.test import APIClient


def test_healthz_view(client: APIClient):
    response = client.get("/_healthz")
    assert response.status_code == status.HTTP_200_OK
    assert response.data == "OK"
