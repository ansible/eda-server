#  Copyright 2024 Red Hat, Inc.
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
from insights_analytics_collector import Package as InsightsAnalyticsPackage

from aap_eda.conf import application_settings

logger = logging.getLogger(__name__)


class MissingUserPasswordError(Exception):
    """Raised when required user credentials are missing."""

    pass


class Package(InsightsAnalyticsPackage):
    """Handles packaging and shipping analytics data to Red Hat services.

    Attributes:
        PAYLOAD_CONTENT_TYPE: MIME type for the analytics payload
        USER_AGENT: Identifier for the analytics client
        CREDENTIAL_SOURCES: Priority list of credential configurations
    """

    PAYLOAD_CONTENT_TYPE = (
        "application/vnd.redhat.aap-event-driven-ansible.filename+tgz"
    )
    USER_AGENT = "EDA-metrics-agent"
    CERT_PATH = settings.INSIGHTS_CERT_PATH
    CREDENTIAL_SOURCES = [
        ("REDHAT", ("REDHAT_USERNAME", "REDHAT_PASSWORD")),
        (
            "SUBSCRIPTIONS",
            ("SUBSCRIPTIONS_USERNAME", "SUBSCRIPTIONS_PASSWORD"),
        ),
    ]

    def _tarname_base(self) -> str:
        timestamp = self.collector.gather_until
        return f'eda-analytics-{timestamp.strftime("%Y-%m-%d-%H%M%S%z")}'

    def get_ingress_url(self) -> str:
        return (
            application_settings.AUTOMATION_ANALYTICS_URL
            or settings.AUTOMATION_ANALYTICS_URL
        )

    def shipping_auth_mode(self) -> str:
        return settings.AUTOMATION_AUTH_METHOD

    def _get_rh_user(self) -> str:
        self._check_users()
        return settings.REDHAT_USERNAME or (
            application_settings.REDHAT_USERNAME
            or application_settings.SUBSCRIPTIONS_USERNAME
        )

    def _get_rh_password(self) -> str:
        self._check_users()
        return settings.REDHAT_PASSWORD or (
            application_settings.REDHAT_PASSWORD
            or application_settings.SUBSCRIPTIONS_PASSWORD
        )

    def _get_http_request_headers(self) -> dict:
        headers = {
            "Content-Type": self.PAYLOAD_CONTENT_TYPE,
            "User-Agent": self.USER_AGENT,
        }
        if hasattr(settings, "EDA_VERSION"):
            headers["X-EDA-Version"] = settings.EDA_VERSION
        return headers

    def _check_users(self) -> None:
        """Validate at least one set of credentials is fully configured.

        Raises:
            MissingUserPasswordError: If no complete credential pairs are found
        """
        has_valid_creds = any(
            getattr(source, user_key, None) and getattr(source, pass_key, None)
            for source in (application_settings, settings)
            for _, (user_key, pass_key) in self.CREDENTIAL_SOURCES
        )

        if not has_valid_creds:
            logger.error(
                "Missing required credentials in application settings"
            )
            raise MissingUserPasswordError(
                "Valid user credentials not found in settings"
            )
