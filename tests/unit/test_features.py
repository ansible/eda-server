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
        settings.DISPATCHERD_FEATURE_FLAG_NAME: [
            {"condition": "boolean", "value": True}
        ],
        settings.ANALYTICS_FEATURE_FLAG_NAME: [
            {"condition": "boolean", "value": False}
        ],
    }

    assert features.DISPATCHERD is True
    assert features.ANALYTICS is False


@pytest.mark.django_db
def test_feature_flag_caching(settings):
    """Test that feature flag values are properly cached."""
    settings.FLAGS = {
        settings.DISPATCHERD_FEATURE_FLAG_NAME: [
            {"condition": "boolean", "value": True}
        ]
    }

    # First access - should cache the value
    assert features.DISPATCHERD is True

    # Change the underlying flag value
    settings.FLAGS[settings.DISPATCHERD_FEATURE_FLAG_NAME][0]["value"] = False

    # Should still get the cached value
    assert features.DISPATCHERD is True


@pytest.mark.django_db
def test_cache_invalidation(settings):
    """Test that cache invalidation works as expected."""
    settings.FLAGS = {
        settings.DISPATCHERD_FEATURE_FLAG_NAME: [
            {"condition": "boolean", "value": True}
        ]
    }

    # Populate cache
    assert features.DISPATCHERD is True

    # Change the flag value and clear cache
    settings.FLAGS[settings.DISPATCHERD_FEATURE_FLAG_NAME][0]["value"] = False
    _get_feature.cache_clear()

    # Should get the new value after cache clear
    assert features.DISPATCHERD is False


@pytest.mark.django_db
def test_invalid_attribute():
    """Test accessing non-existent feature flag raises AttributeError."""
    with pytest.raises(AttributeError) as excinfo:
        _ = features.NON_EXISTENT_FEATURE
    assert "has no attribute NON_EXISTENT_FEATURE" in str(excinfo.value)
