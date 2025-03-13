import pytest
from ansible_base.lib.dynamic_config import toggle_feature_flags
from django.conf import settings
from django.test import override_settings
from flags.state import flag_state
from rest_framework import status

from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_feature_flags_list_endpoint(admin_client):
    response = admin_client.get(f"{api_url_v1}/feature_flags_state/")
    assert response.status_code == status.HTTP_200_OK, response.data
    # Test number of feature flags.
    # Modify each time a flag is added to default settings
    assert len(response.data) == 0


@override_settings(
    FLAGS={
        "FEATURE_SOME_PLATFORM_FLAG_ENABLED": [
            {"condition": "boolean", "value": False, "required": True},
            {"condition": "before date", "value": "2022-06-01T12:00Z"},
        ],
        "FEATURE_SOME_PLATFORM_FLAG_FOO_ENABLED": [
            {"condition": "boolean", "value": True},
            {"condition": "before date", "value": "2022-06-01T12:00Z"},
        ],
    }
)
@pytest.mark.django_db
def test_feature_flags_override_flags(admin_client):
    response = admin_client.get(f"{api_url_v1}/feature_flags_state/")
    assert response.status_code == status.HTTP_200_OK, response.data
    assert len(response.data) == 2  # Validates number of feature flags
    assert response.data["FEATURE_SOME_PLATFORM_FLAG_ENABLED"] is False
    assert response.data["FEATURE_SOME_PLATFORM_FLAG_FOO_ENABLED"] is True


@override_settings(
    FLAGS={
        "FEATURE_SOME_PLATFORM_FLAG_ENABLED": [
            {"condition": "boolean", "value": False},
        ],
    },
    FEATURE_SOME_PLATFORM_FLAG_ENABLED=True,
)
@pytest.mark.django_db
def test_feature_flags_toggle():
    settings_override = {
        "FLAGS": settings.FLAGS,
        "FEATURE_SOME_PLATFORM_FLAG_ENABLED": settings.FEATURE_SOME_PLATFORM_FLAG_ENABLED,  # noqa: E501
    }
    assert toggle_feature_flags(settings_override) == {
        "FLAGS__FEATURE_SOME_PLATFORM_FLAG_ENABLED": [
            {"condition": "boolean", "value": True},
        ]
    }
    assert flag_state("FEATURE_SOME_PLATFORM_FLAG_ENABLED") is True
