from unittest import mock

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from tests.integration.constants import api_url_v1


class FallbackException(Exception):
    pass


def raise_exception(self, request):
    raise FallbackException


@pytest.mark.django_db
@mock.patch("aap_eda.api.views.project.ProjectViewSet.list", new=raise_exception)
def test_debug_unexpected_exception(client: APIClient, settings):
    settings.DEBUG = True
    with pytest.raises(FallbackException):
        client.get(f"{api_url_v1}/projects/")


@pytest.mark.django_db
@mock.patch("aap_eda.api.views.project.ProjectViewSet.list", new=raise_exception)
def test_non_debug_unexpected_exception(client: APIClient, settings):
    settings.DEBUG = False
    response = client.get(f"{api_url_v1}/projects/")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    data = response.json()
    assert data["detail"].startswith("Unexpected server error")
