import pytest
from ansible_base.feature_flags.models import AAPFlag
from ansible_base.feature_flags.utils import (
    create_initial_data as seed_feature_flags,
)
from django.conf import settings
from flags.state import flag_state, get_flags
from rest_framework import status

from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_feature_flags_list_endpoint(admin_client):
    response = admin_client.get(f"{api_url_v1}/feature_flags_state/")
    assert response.status_code == status.HTTP_200_OK, response.data
    # Validates expected default feature flags
    # Modify each time a flag is added to default settings
    assert len(response.data) == len(get_flags())
    assert response.data[settings.ANALYTICS_FEATURE_FLAG_NAME] is False


@pytest.mark.parametrize("flag_value", [True, False])
@pytest.mark.django_db
def test_feature_flags_toggle(flag_value):
    flag_name = "FEATURE_EDA_ANALYTICS_ENABLED"
    setattr(settings, flag_name, flag_value)
    AAPFlag.objects.all().delete()
    seed_feature_flags()
    assert flag_state(flag_name) is flag_value
