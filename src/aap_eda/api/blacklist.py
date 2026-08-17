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

    Supports both global (pre-org-resolution) and per-org modes.

    Global mode uses Dynaconf settings and flat cache keys. Per-org
    mode reads thresholds from the EventStreamSetting DB model
    (cached) and uses org-namespaced cache keys for isolation.
    """

    FAILURE_PREFIX = "es_fail"
    BLACKLIST_PREFIX = "es_blacklist"

    def check_blacklist(self, client_ip: str) -> None:
        """Global blacklist check (pre-org-resolution).

        Used before the EventStream UUID is resolved, when the
        organization is unknown. Checks global Dynaconf settings.

        A threshold of 0 disables blacklist checking entirely.
        """
        if settings.EVENT_STREAM_BLACKLIST_THRESHOLD == 0:
            return
        key = f"{self.BLACKLIST_PREFIX}:{client_ip}"
        if cache.get(key):
            raise AuthenticationFailed("Too many failed attempts")

    def check_ip_policy(self, client_ip: str, org_id: int) -> None:
        """Full per-org IP policy check.

        Order:
        1. Admin-managed blocked_ips (DB, cached)
        2. Auto-blacklist from cache
        3. Allowlist enforcement (if non-empty)
        """
        from aap_eda.services.event_stream_settings_cache import (
            get_org_settings,
        )

        org_settings = get_org_settings(org_id)

        if client_ip in org_settings["blocked_ips"]:
            raise AuthenticationFailed("IP address is blocked")

        threshold = org_settings["blacklist_threshold"]
        if threshold > 0:
            key = f"{self.BLACKLIST_PREFIX}:{org_id}:{client_ip}"
            if cache.get(key):
                raise AuthenticationFailed("Too many failed attempts")

        if (
            org_settings["allowed_ips"]
            and client_ip not in org_settings["allowed_ips"]
        ):
            raise AuthenticationFailed("IP address not in allowlist")

    def record_failure(
        self, client_ip: str, org_id: int | None = None
    ) -> None:
        """Record a failed request from the given IP.

        When org_id is provided, uses per-org settings and
        org-namespaced cache keys. Otherwise falls back to global
        Dynaconf settings (for pre-org-resolution failures like
        bad UUID lookups).
        """
        if org_id is not None:
            from aap_eda.services.event_stream_settings_cache import (
                get_org_settings,
            )

            org_settings = get_org_settings(org_id)
            threshold = org_settings["blacklist_threshold"]
            window = org_settings["blacklist_window"]
            duration = org_settings["lockout_duration"]
            key_suffix = f"{org_id}:{client_ip}"
        else:
            threshold = settings.EVENT_STREAM_BLACKLIST_THRESHOLD
            window = settings.EVENT_STREAM_BLACKLIST_WINDOW
            duration = settings.EVENT_STREAM_BLACKLIST_DURATION
            key_suffix = client_ip

        if threshold == 0:
            return

        counter_key = f"{self.FAILURE_PREFIX}:{key_suffix}"
        try:
            failures = cache.incr(counter_key)
        except ValueError:
            cache.set(counter_key, 1, window)
            failures = 1

        if failures >= threshold:
            blacklist_key = f"{self.BLACKLIST_PREFIX}:{key_suffix}"
            cache.set(blacklist_key, True, duration)
            logger.warning(
                "Blacklisted IP %s (org=%s) after %d failures",
                client_ip,
                org_id,
                failures,
            )
            cache.delete(counter_key)
