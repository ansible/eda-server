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

import logging

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)


class BlacklistManager:
    """Rate-limit and blacklist IPs that fail event stream authentication.

    Tracks auth failures and invalid UUID probes per client IP using
    Django's cache framework. All entries are evicted automatically
    by cache TTL — no manual cleanup required.
    """

    FAILURE_PREFIX = "es_fail"
    BLACKLIST_PREFIX = "es_blacklist"

    def check_blacklist(self, client_ip: str) -> None:
        """Raise AuthenticationFailed if the IP is globally blacklisted.

        A threshold of 0 disables blacklist checking entirely.
        """
        if settings.EVENT_STREAM_BLACKLIST_THRESHOLD == 0:
            return
        key = f"{self.BLACKLIST_PREFIX}:{client_ip}"
        if cache.get(key):
            raise AuthenticationFailed("Too many failed attempts")

    def record_failure(self, client_ip: str) -> None:
        """Record a failed request from the given IP.

        All failure types (bad credentials, invalid UUIDs) count
        toward the same threshold. After
        EVENT_STREAM_BLACKLIST_THRESHOLD failures within
        EVENT_STREAM_BLACKLIST_WINDOW seconds, the IP is globally
        blacklisted for EVENT_STREAM_BLACKLIST_DURATION seconds.
        A threshold of 0 disables blacklisting.
        """
        if settings.EVENT_STREAM_BLACKLIST_THRESHOLD == 0:
            return
        counter_key = f"{self.FAILURE_PREFIX}:{client_ip}"
        try:
            failures = cache.incr(counter_key)
        except ValueError:
            cache.set(
                counter_key,
                1,
                settings.EVENT_STREAM_BLACKLIST_WINDOW,
            )
            failures = 1

        if failures >= settings.EVENT_STREAM_BLACKLIST_THRESHOLD:
            blacklist_key = f"{self.BLACKLIST_PREFIX}:{client_ip}"
            cache.set(
                blacklist_key,
                True,
                settings.EVENT_STREAM_BLACKLIST_DURATION,
            )
            logger.warning(
                "Globally blacklisted IP %s after %d failures",
                client_ip,
                failures,
            )
            cache.delete(counter_key)
