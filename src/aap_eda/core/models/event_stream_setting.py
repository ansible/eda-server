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

from django.db import models

from .base import PrimordialModel


class EventStreamSetting(PrimordialModel):
    """Per-organization IP security settings for event streams.

    Controls which IPs may post events (allowlist), which are
    permanently blocked (blocklist), and auto-blacklist behavior
    (threshold, window, lockout duration).
    """

    class Meta:
        db_table = "core_event_stream_setting"
        ordering = ("-created_at",)

    organization = models.OneToOneField(
        "Organization",
        on_delete=models.CASCADE,
        related_name="event_stream_setting",
    )
    allowed_ips = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "IP allowlist. When non-empty, only these IPs may post "
            "events to any event stream in this organization."
        ),
    )
    blocked_ips = models.JSONField(
        default=list,
        blank=True,
        help_text="Admin-managed list of permanently blocked IPs.",
    )
    blacklist_threshold = models.PositiveIntegerField(
        default=5,
        help_text=(
            "Number of auth failures before an IP is auto-blacklisted. "
            "Set to 0 to disable auto-blacklisting."
        ),
    )
    blacklist_window = models.PositiveIntegerField(
        default=60,
        help_text="Seconds within which failures are counted.",
    )
    lockout_duration = models.PositiveIntegerField(
        default=3600,
        help_text="Seconds an auto-blacklisted IP stays blocked.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
