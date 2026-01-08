#  Copyright 2025 Red Hat, Inc.
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

"""Unit tests for feature flags functionality."""

import pytest
from ansible_base.feature_flags.models import AAPFlag
from ansible_base.feature_flags.utils import (
    create_initial_data as seed_feature_flags,
)

from aap_eda.settings import features
from aap_eda.settings.features import _get_feature


@pytest.fixture(autouse=True)
def clear_feature_cache():
    """Clear the feature flag cache before each test."""
    _get_feature.cache_clear()


@pytest.mark.django_db
def test_get_feature_flag(settings):
    """Test getting feature flag values."""
    AAPFlag.objects.filter(name=settings.ANALYTICS_FEATURE_FLAG_NAME).delete()
    setattr(settings, settings.ANALYTICS_FEATURE_FLAG_NAME, False)
    seed_feature_flags()

    assert features.ANALYTICS is False


@pytest.mark.django_db
def test_feature_flag_caching(settings):
    """Test that feature flag values are properly cached."""
    AAPFlag.objects.filter(name=settings.ANALYTICS_FEATURE_FLAG_NAME).delete()
    setattr(settings, settings.ANALYTICS_FEATURE_FLAG_NAME, True)
    seed_feature_flags()
    # Clear cache to ensure settings are picked up
    _get_feature.cache_clear()

    # First access - should cache the value
    features.ANALYTICS

    # Change the underlying flag value
    setattr(settings, settings.ANALYTICS_FEATURE_FLAG_NAME, False)
    seed_feature_flags()
    # Should still get the cached value
    assert features.ANALYTICS is True


@pytest.mark.django_db
def test_cache_invalidation(settings):
    """Test that cache invalidation works as expected."""
    AAPFlag.objects.filter(name=settings.ANALYTICS_FEATURE_FLAG_NAME).delete()
    setattr(settings, settings.ANALYTICS_FEATURE_FLAG_NAME, True)
    seed_feature_flags()

    # Populate cache
    assert features.ANALYTICS is True

    # Change the flag value and clear cache
    setattr(settings, settings.ANALYTICS_FEATURE_FLAG_NAME, False)
    seed_feature_flags()
    _get_feature.cache_clear()

    # Feature should remain true.
    # If runtime toggle, we should only be able to
    # update the value after toggling it via the platform gateway
    assert features.ANALYTICS is True


@pytest.mark.django_db
def test_invalid_attribute():
    """Test accessing non-existent feature flag raises AttributeError."""
    with pytest.raises(AttributeError) as excinfo:
        _ = features.NON_EXISTENT_FEATURE
    assert "has no attribute NON_EXISTENT_FEATURE" in str(excinfo.value)
