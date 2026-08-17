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
from rest_framework.exceptions import AuthenticationFailed

from aap_eda.api.blacklist import BlacklistManager
from aap_eda.core import models


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def manager():
    return BlacklistManager()


@pytest.fixture
def blacklist_settings(settings):
    settings.EVENT_STREAM_BLACKLIST_THRESHOLD = 5
    settings.EVENT_STREAM_BLACKLIST_WINDOW = 60
    settings.EVENT_STREAM_BLACKLIST_DURATION = 3600
    return settings


@pytest.mark.django_db
class TestCheckIpPolicy:
    def test_blocked_ip_rejected(
        self, manager, default_organization, blacklist_settings
    ):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            blocked_ips=["10.0.0.1"],
        )
        with pytest.raises(AuthenticationFailed, match="blocked"):
            manager.check_ip_policy("10.0.0.1", default_organization.id)

    def test_unblocked_ip_passes(
        self, manager, default_organization, blacklist_settings
    ):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            blocked_ips=["10.0.0.1"],
        )
        manager.check_ip_policy("10.0.0.2", default_organization.id)

    def test_allowed_ips_enforced(
        self, manager, default_organization, blacklist_settings
    ):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            allowed_ips=["10.0.0.1", "10.0.0.2"],
        )
        with pytest.raises(AuthenticationFailed, match="allowlist"):
            manager.check_ip_policy("10.0.0.99", default_organization.id)

    def test_allowed_ips_passes_listed_ip(
        self, manager, default_organization, blacklist_settings
    ):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            allowed_ips=["10.0.0.1"],
        )
        manager.check_ip_policy("10.0.0.1", default_organization.id)

    def test_empty_allowed_ips_allows_all(
        self, manager, default_organization, blacklist_settings
    ):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            allowed_ips=[],
        )
        manager.check_ip_policy("10.0.0.99", default_organization.id)

    def test_auto_blacklisted_ip_rejected(
        self, manager, default_organization, blacklist_settings
    ):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            blacklist_threshold=2,
        )
        org_id = default_organization.id
        manager.record_failure("10.0.0.1", org_id=org_id)
        manager.record_failure("10.0.0.1", org_id=org_id)
        with pytest.raises(AuthenticationFailed, match="Too many"):
            manager.check_ip_policy("10.0.0.1", org_id)

    def test_no_settings_row_uses_global_defaults(
        self, manager, default_organization, blacklist_settings
    ):
        manager.check_ip_policy("10.0.0.1", default_organization.id)


@pytest.mark.django_db
class TestOrgAwareRecordFailure:
    def test_per_org_threshold(
        self, manager, default_organization, blacklist_settings
    ):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            blacklist_threshold=2,
            blacklist_window=60,
            lockout_duration=3600,
        )
        org_id = default_organization.id
        manager.record_failure("10.0.0.1", org_id=org_id)
        manager.record_failure("10.0.0.1", org_id=org_id)
        key = f"es_blacklist:{org_id}:10.0.0.1"
        assert cache.get(key) is True

    def test_org_isolation(self, manager, blacklist_settings):
        org_a = models.Organization.objects.create(name="Org A")
        org_b = models.Organization.objects.create(name="Org B")
        models.EventStreamSetting.objects.create(
            organization=org_a, blacklist_threshold=2
        )
        models.EventStreamSetting.objects.create(
            organization=org_b, blacklist_threshold=2
        )
        manager.record_failure("10.0.0.1", org_id=org_a.id)
        manager.record_failure("10.0.0.1", org_id=org_a.id)
        manager.check_ip_policy("10.0.0.1", org_b.id)

    def test_zero_threshold_disables(
        self, manager, default_organization, blacklist_settings
    ):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            blacklist_threshold=0,
        )
        org_id = default_organization.id
        for _ in range(10):
            manager.record_failure("10.0.0.1", org_id=org_id)
        manager.check_ip_policy("10.0.0.1", org_id)

    def test_global_fallback_without_org_id(self, manager, blacklist_settings):
        blacklist_settings.EVENT_STREAM_BLACKLIST_THRESHOLD = 2
        manager.record_failure("10.0.0.1")
        manager.record_failure("10.0.0.1")
        with pytest.raises(AuthenticationFailed):
            manager.check_blacklist("10.0.0.1")
