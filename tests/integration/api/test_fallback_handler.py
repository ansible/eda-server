from unittest import mock

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from tests.integration.constants import api_url_v1


class FallbackException(Exception):
    pass


def raise_exception(self, request):
    raise FallbackException


@pytest.mark.django_db
@mock.patch(
    "aap_eda.api.views.project.ProjectViewSet.list", new=raise_exception
)
def test_debug_unexpected_exception(admin_client: APIClient, settings):
    with override_settings(DEBUG=True):
        with pytest.raises(FallbackException):
            admin_client.get(f"{api_url_v1}/projects/")


@pytest.mark.django_db
@mock.patch(
    "aap_eda.api.views.project.ProjectViewSet.list", new=raise_exception
)
def test_non_debug_unexpected_exception(admin_client: APIClient, settings):
    with override_settings(DEBUG=False):
        response = admin_client.get(f"{api_url_v1}/projects/")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        data = response.json()
        assert data["detail"].startswith("Unexpected server error")
