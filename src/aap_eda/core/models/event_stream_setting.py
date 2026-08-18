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

    Controls which IPs may post events (allowlist) and tracks
    IPs that attempted access and were rejected (blocklist).
    Admins can promote blocked IPs to the allowlist or remove
    them from the blocklist entirely.
    """

    class Meta:
        db_table = "core_event_stream_setting"
        ordering = ("-created_at",)
        default_permissions = ("add", "change", "view")

    organization = models.OneToOneField(
        "Organization",
        on_delete=models.CASCADE,
        related_name="event_stream_setting",
    )
    allowed_ips = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "IP allowlist. Accepts individual IPs and CIDR "
            "ranges (e.g. 192.30.252.0/22). When non-empty, "
            "only matching IPs may post events. "
            "Empty means all IPs are allowed."
        ),
    )
    blocked_ips = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "IPs that attempted access and were rejected. "
            "Auto-populated on failed requests for admin visibility."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
