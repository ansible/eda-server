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


@pytest.mark.django_db
class TestCheckIpPolicy:
    def test_no_settings_allows_all(self, manager, default_organization):
        manager.check_ip_policy("10.0.0.1", default_organization.id)

    def test_empty_allowlist_allows_all(self, manager, default_organization):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            allowed_ips=[],
        )
        manager.check_ip_policy("10.0.0.1", default_organization.id)

    def test_allowlist_rejects_unlisted_ip(
        self, manager, default_organization
    ):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            allowed_ips=["10.0.0.1"],
        )
        with pytest.raises(AuthenticationFailed, match="allowlist"):
            manager.check_ip_policy("10.0.0.99", default_organization.id)

    def test_allowlist_passes_listed_ip(self, manager, default_organization):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            allowed_ips=["10.0.0.1"],
        )
        manager.check_ip_policy("10.0.0.1", default_organization.id)

    def test_cidr_allows_ip_in_range(self, manager, default_organization):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            allowed_ips=["192.30.252.0/22"],
        )
        manager.check_ip_policy("192.30.253.5", default_organization.id)

    def test_cidr_rejects_ip_outside_range(
        self, manager, default_organization
    ):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            allowed_ips=["192.30.252.0/22"],
        )
        with pytest.raises(AuthenticationFailed, match="allowlist"):
            manager.check_ip_policy("10.0.0.1", default_organization.id)

    def test_mixed_ips_and_cidrs(self, manager, default_organization):
        models.EventStreamSetting.objects.create(
            organization=default_organization,
            allowed_ips=["10.0.0.1", "192.30.252.0/22"],
        )
        manager.check_ip_policy("10.0.0.1", default_organization.id)
        manager.check_ip_policy("192.30.255.100", default_organization.id)


@pytest.mark.django_db
class TestRecordBlockedIp:
    def test_records_rejected_ip(self, manager, default_organization):
        setting = models.EventStreamSetting.objects.create(
            organization=default_organization,
        )
        manager.record_blocked_ip("10.0.0.1", default_organization.id)
        setting.refresh_from_db()
        assert "10.0.0.1" in setting.blocked_ips

    def test_does_not_duplicate(self, manager, default_organization):
        setting = models.EventStreamSetting.objects.create(
            organization=default_organization,
            blocked_ips=["10.0.0.1"],
        )
        manager.record_blocked_ip("10.0.0.1", default_organization.id)
        setting.refresh_from_db()
        assert setting.blocked_ips.count("10.0.0.1") == 1

    def test_no_settings_row_is_noop(self, manager, default_organization):
        manager.record_blocked_ip("10.0.0.1", default_organization.id)
