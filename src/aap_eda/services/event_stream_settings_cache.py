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

"""Per-organization event stream settings cache.

Settings are cached for SETTINGS_CACHE_TTL seconds. A post_save
signal on EventStreamSetting invalidates the cache so changes
propagate immediately (within the same cache backend).
"""

import logging
from typing import Any, Optional

from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

SETTINGS_CACHE_PREFIX = "es_org_settings"
SETTINGS_CACHE_TTL = 300
_CACHE_MISS = object()


def _cache_key(org_id: int) -> str:
    return f"{SETTINGS_CACHE_PREFIX}:{org_id}"  # noqa: E231


def get_org_settings(org_id: int) -> Optional[dict]:
    """Get per-org event stream settings, from cache or DB.

    Returns None if no settings row exists for this org
    (meaning no IP restrictions are configured).
    """
    key = _cache_key(org_id)
    cached = cache.get(key, _CACHE_MISS)
    if cached is not _CACHE_MISS:
        return cached

    from aap_eda.core.models import EventStreamSetting

    try:
        setting = EventStreamSetting.objects.get(organization_id=org_id)
        data = {
            "allowed_ips": set(setting.allowed_ips),
            "blocked_ips": set(setting.blocked_ips),
        }
    except EventStreamSetting.DoesNotExist:
        data = None

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
