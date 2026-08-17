#  Copyright 2026 Red Hat, Inc.
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

import pytest
from django.core.cache import cache

from aap_eda.core import models
from aap_eda.services.event_stream_settings_cache import (
    get_org_settings,
    invalidate_org_settings,
)


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestGetOrgSettings:
    def test_returns_db_values(self, default_organization):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            allowed_ips=["10.0.0.1", "10.0.0.2"],
            blocked_ips=["192.168.1.100"],
            blacklist_threshold=3,
            blacklist_window=30,
            lockout_duration=1800,
        )
        result = get_org_settings(default_organization.id)
        assert result["allowed_ips"] == {"10.0.0.1", "10.0.0.2"}
        assert result["blocked_ips"] == {"192.168.1.100"}
        assert result["blacklist_threshold"] == 3
        assert result["blacklist_window"] == 30
        assert result["lockout_duration"] == 1800

    def test_caches_result(self, default_organization):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            allowed_ips=["10.0.0.1"],
        )
        result1 = get_org_settings(default_organization.id)
        models.EventStreamSetting.objects.filter(
            organization=default_organization
        ).update(allowed_ips=["10.0.0.99"])
        result2 = get_org_settings(default_organization.id)
        assert result1["allowed_ips"] == result2["allowed_ips"]

    def test_fallback_to_global_defaults(self, default_organization, settings):
        settings.EVENT_STREAM_BLACKLIST_THRESHOLD = 7
        settings.EVENT_STREAM_BLACKLIST_WINDOW = 120
        settings.EVENT_STREAM_BLACKLIST_DURATION = 7200
        result = get_org_settings(default_organization.id)
        assert result["allowed_ips"] == set()
        assert result["blocked_ips"] == set()
        assert result["blacklist_threshold"] == 7
        assert result["blacklist_window"] == 120
        assert result["lockout_duration"] == 7200

    def test_invalidate_clears_cache(self, default_organization):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            allowed_ips=["10.0.0.1"],
        )
        get_org_settings(default_organization.id)
        invalidate_org_settings(default_organization.id)
        models.EventStreamSetting.objects.filter(
            organization=default_organization
        ).update(allowed_ips=["10.0.0.99"])
        result = get_org_settings(default_organization.id)
        assert result["allowed_ips"] == {"10.0.0.99"}


@pytest.mark.django_db
class TestSignalInvalidation:
    def test_post_save_invalidates_cache(self, default_organization):
        setting = models.EventStreamSetting.objects.create(
            organization=default_organization,
            allowed_ips=["10.0.0.1"],
        )
        get_org_settings(default_organization.id)
        setting.allowed_ips = ["10.0.0.99"]
        setting.save()
        result = get_org_settings(default_organization.id)
        assert result["allowed_ips"] == {"10.0.0.99"}
