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

import ipaddress
import logging

from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)

MAX_BLOCKED_IPS = 1000


def normalize_ip(ip_str: str) -> str:
    """Normalize an IP address string.

    Converts IPv4-mapped IPv6 addresses (e.g. ::ffff:10.0.0.1)
    to their IPv4 form so allowlist lookups match regardless of
    how the proxy reports the client IP.
    """
    try:
        addr = ipaddress.ip_address(ip_str.strip())
    except ValueError:
        return ip_str.strip()
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        return str(addr.ipv4_mapped)
    return str(addr)


def ip_in_allowlist(client_ip: str, allowed_ips: set) -> bool:
    """Check if an IP matches any entry in the allowlist.

    Supports both individual IPs and CIDR ranges.
    """
    if client_ip in allowed_ips:
        return True
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for entry in allowed_ips:
        if "/" in entry:
            try:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            except ValueError:
                continue
    return False


class BlacklistManager:
    """Allowlist-based IP policy for event streams.

    When an organization has configured allowed_ips, only those
    IPs may post events. IPs that are rejected are recorded in
    blocked_ips for admin visibility — admins can then promote
    a blocked IP to the allowlist or remove it entirely.

    When no EventStreamSetting row exists for the org, or the
    allowed_ips list is empty, all IPs are permitted.
    """

    def check_ip_policy(self, client_ip: str, org_id: int) -> None:
        """Check if the IP is allowed for this organization.

        Raises AuthenticationFailed if the org has a non-empty
        allowlist and the IP is not in it.
        """
        from aap_eda.services.event_stream_settings_cache import (
            get_org_settings,
        )

        org_settings = get_org_settings(org_id)
        if org_settings is None:
            return

        normalized = normalize_ip(client_ip)

        if org_settings["allowed_ips"] and not ip_in_allowlist(
            normalized, org_settings["allowed_ips"]
        ):
            self.record_blocked_ip(normalized, org_id)
            raise AuthenticationFailed("IP address not in allowlist")

    def record_blocked_ip(self, client_ip: str, org_id: int) -> None:
        """Add an IP to the org's blocked_ips list for visibility.

        Only adds the IP if it is not already tracked. Caps the
        list at MAX_BLOCKED_IPS to prevent unbounded growth.
        """
        from aap_eda.core.models import EventStreamSetting

        normalized = normalize_ip(client_ip)

        try:
            setting = EventStreamSetting.objects.get(organization_id=org_id)
        except EventStreamSetting.DoesNotExist:
            return

        if normalized in setting.blocked_ips:
            return

        if len(setting.blocked_ips) >= MAX_BLOCKED_IPS:
            logger.warning(
                "Blocked IPs cap (%d) reached for org %s",
                MAX_BLOCKED_IPS,
                org_id,
            )
            return

        setting.blocked_ips = [*setting.blocked_ips, normalized]
        setting.save(update_fields=["blocked_ips", "modified_at"])
        logger.info(
            "Recorded blocked IP %s for org %s",
            normalized,
            org_id,
        )
