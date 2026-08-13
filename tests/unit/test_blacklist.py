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


class TestBlacklisting:
    def test_single_failure_not_blacklisted(self, manager, blacklist_settings):
        manager.record_failure("10.0.0.1")
        manager.check_blacklist("10.0.0.1")

    def test_threshold_triggers_blacklist(self, manager, blacklist_settings):
        blacklist_settings.EVENT_STREAM_BLACKLIST_THRESHOLD = 3

        for _ in range(3):
            manager.record_failure("10.0.0.1")

        with pytest.raises(AuthenticationFailed):
            manager.check_blacklist("10.0.0.1")

    def test_below_threshold_not_blacklisted(
        self, manager, blacklist_settings
    ):
        for _ in range(4):
            manager.record_failure("10.0.0.1")

        manager.check_blacklist("10.0.0.1")

    def test_per_ip_isolation(self, manager, blacklist_settings):
        blacklist_settings.EVENT_STREAM_BLACKLIST_THRESHOLD = 3

        for _ in range(3):
            manager.record_failure("10.0.0.1")

        manager.check_blacklist("10.0.0.2")

    def test_clean_ip_passes(self, manager):
        manager.check_blacklist("10.0.0.1")


class TestDisabledBlacklisting:
    def test_zero_threshold_disables_blacklisting(
        self, manager, blacklist_settings
    ):
        blacklist_settings.EVENT_STREAM_BLACKLIST_THRESHOLD = 0

        for _ in range(10):
            manager.record_failure("10.0.0.1")

        manager.check_blacklist("10.0.0.1")
