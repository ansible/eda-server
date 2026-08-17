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

"""Per-organization event stream settings cache with signal-based invalidation.

Settings are cached for SETTINGS_CACHE_TTL seconds. A post_save signal
on EventStreamSetting invalidates the cache so changes propagate
immediately (within the same cache backend).
"""

import logging
from typing import Any

from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

SETTINGS_CACHE_PREFIX = "es_org_settings"
SETTINGS_CACHE_TTL = 300


def _cache_key(org_id: int) -> str:
    return f"{SETTINGS_CACHE_PREFIX}:{org_id}"


def get_org_settings(org_id: int) -> dict:
    """Get per-org event stream settings, from cache or DB.

    Falls back to global Dynaconf defaults if no DB row exists
    for the given organization.
    """
    key = _cache_key(org_id)
    cached = cache.get(key)
    if cached is not None:
        return cached

    from aap_eda.core.models import EventStreamSetting

    try:
        setting = EventStreamSetting.objects.get(organization_id=org_id)
        data = {
            "allowed_ips": set(setting.allowed_ips),
            "blocked_ips": set(setting.blocked_ips),
            "blacklist_threshold": setting.blacklist_threshold,
            "blacklist_window": setting.blacklist_window,
            "lockout_duration": setting.lockout_duration,
        }
    except EventStreamSetting.DoesNotExist:
        from django.conf import settings as django_settings

        data = {
            "allowed_ips": set(),
            "blocked_ips": set(),
            "blacklist_threshold": getattr(
                django_settings, "EVENT_STREAM_BLACKLIST_THRESHOLD", 5
            ),
            "blacklist_window": getattr(
                django_settings, "EVENT_STREAM_BLACKLIST_WINDOW", 60
            ),
            "lockout_duration": getattr(
                django_settings, "EVENT_STREAM_BLACKLIST_DURATION", 3600
            ),
        }

    cache.set(key, data, SETTINGS_CACHE_TTL)
    return data


def invalidate_org_settings(org_id: int) -> None:
    """Delete the cached settings for an organization."""
    cache.delete(_cache_key(org_id))


@receiver(post_save, sender="core.EventStreamSetting")
def on_event_stream_setting_saved(
    sender: Any,
    instance: Any,
    **kwargs: Any,
) -> None:
    """Invalidate cache when settings are saved."""
    invalidate_org_settings(instance.organization_id)
    logger.info(
        "Invalidated event stream settings cache for org %s",
        instance.organization_id,
    )
