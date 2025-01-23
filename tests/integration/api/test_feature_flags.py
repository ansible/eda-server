import pytest
from django.test import override_settings
from rest_framework import status

from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_feature_flags_list_endpoint(admin_client):
    response = admin_client.get(f"{api_url_v1}/feature-flags/definition")
    assert response.status_code == status.HTTP_200_OK, response.data
    # Test number of feature flags.
    # Modify each time a flag is added to default settings
    assert len(response.data) == 0


@override_settings(
    FLAGS={
        "FEATURE_SOME_PLATFORM_FLAG_ENABLED": [
            {"condition": "boolean", "value": False, "required": True},
            {"condition": "before date", "value": "2022-06-01T12:00Z"},
        ]
    }
)
@pytest.mark.django_db
def test_feature_flags_override_flags(admin_client):
    response = admin_client.get(f"{api_url_v1}/feature-flags/definition")
    assert response.status_code == status.HTTP_200_OK, response.data
    assert len(response.data) == 1  # Validates number of feature flags
    assert (
        len(response.data["FEATURE_SOME_PLATFORM_FLAG_ENABLED"]) == 2
    )  # Validates number of conditions
