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
class TestOrgIsolation:
    def test_separate_allowlists(self, manager):
        org_a = models.Organization.objects.create(name="A")
        org_b = models.Organization.objects.create(name="B")
        models.EventStreamSetting.objects.create(
            organization=org_a,
            allowed_ips=["10.0.0.1"],
        )
        models.EventStreamSetting.objects.create(
            organization=org_b,
            allowed_ips=["10.0.0.2"],
        )
        manager.check_ip_policy("10.0.0.1", org_a.id)
        with pytest.raises(AuthenticationFailed):
            manager.check_ip_policy("10.0.0.1", org_b.id)

    def test_blocked_ips_per_org(self, manager):
        org_a = models.Organization.objects.create(name="A")
        org_b = models.Organization.objects.create(name="B")
        setting_a = models.EventStreamSetting.objects.create(
            organization=org_a,
        )
        models.EventStreamSetting.objects.create(
            organization=org_b,
        )
        manager.record_blocked_ip("10.0.0.1", org_a.id)
        setting_a.refresh_from_db()
        setting_b = models.EventStreamSetting.objects.get(organization=org_b)
        assert "10.0.0.1" in setting_a.blocked_ips
        assert "10.0.0.1" not in setting_b.blocked_ips


@pytest.mark.django_db
class TestAllowlistRejectsAndRecords:
    def test_rejection_auto_records_blocked_ip(
        self, manager, default_organization
    ):
        setting = models.EventStreamSetting.objects.create(
            organization=default_organization,
            allowed_ips=["10.0.0.1"],
        )
        with pytest.raises(AuthenticationFailed):
            manager.check_ip_policy("10.0.0.99", default_organization.id)
        setting.refresh_from_db()
        assert "10.0.0.99" in setting.blocked_ips
