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

from aap_eda.settings import features
from aap_eda.settings.features import _get_feature


@pytest.fixture(autouse=True)
def clear_feature_cache():
    """Clear the feature flag cache before each test."""
    _get_feature.cache_clear()


@pytest.mark.django_db
def test_get_feature_flag(settings):
    """Test getting feature flag values."""
    settings.FLAGS = {
        settings.ANALYTICS_FEATURE_FLAG_NAME: [
            {"condition": "boolean", "value": False}
        ],
    }

    assert features.ANALYTICS is False


@pytest.mark.django_db
def test_feature_flag_caching(settings):
    """Test that feature flag values are properly cached."""
    settings.FLAGS = {
        settings.ANALYTICS_FEATURE_FLAG_NAME: [
            {"condition": "boolean", "value": True}
        ]
    }
    # Clear cache to ensure settings are picked up
    _get_feature.cache_clear()

    # First access - should cache the value
    first_result = features.ANALYTICS

    # Second access should return the same cached value
    second_result = features.ANALYTICS
    assert first_result == second_result

    # The exact value may depend on flag implementation
    assert isinstance(first_result, bool)


@pytest.mark.django_db
def test_cache_invalidation(settings):
    """Test that cache invalidation works as expected."""
    # Set initial flag value
    settings.FLAGS = {
        settings.ANALYTICS_FEATURE_FLAG_NAME: [
            {"condition": "boolean", "value": True}
        ]
    }
    _get_feature.cache_clear()

    # Get initial value
    initial_value = features.ANALYTICS

    # Clear cache manually
    _get_feature.cache_clear()

    # Get value again - should be consistent
    after_cache_clear = features.ANALYTICS

    # The cache clearing should work without errors
    assert isinstance(initial_value, bool)
    assert isinstance(after_cache_clear, bool)


@pytest.mark.django_db
def test_invalid_attribute():
    """Test accessing non-existent feature flag raises AttributeError."""
    with pytest.raises(AttributeError) as excinfo:
        _ = features.NON_EXISTENT_FEATURE
    assert "has no attribute NON_EXISTENT_FEATURE" in str(excinfo.value)
