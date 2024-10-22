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
from django.conf import settings
from insights_analytics_collector import Package as InsightsAnalyticsPackage

from aap_eda.conf import application_settings


class MissingUserPasswordError(Exception):
    pass


class Package(InsightsAnalyticsPackage):
    PAYLOAD_CONTENT_TYPE = "application/vnd.redhat.aap-eda.filename+tgz"
    CERT_PATH = settings.INSIGHTS_CERT_PATH

    def _tarname_base(self) -> str:
        timestamp = self.collector.gather_until
        return f'eda-analytics-{timestamp.strftime("%Y-%m-%d-%H%M%S%z")}'

    def get_ingress_url(self) -> str:
        return application_settings.AUTOMATION_ANALYTICS_URL

    def shipping_auth_mode(self) -> str:
        return settings.AUTOMATION_AUTH_METHOD

    def _get_rh_user(self) -> str:
        self._check_users()
        user_name = (
            application_settings.REDHAT_USERNAME
            or application_settings.SUBSCRIPTIONS_USERNAME
        )

        return user_name

    def _get_rh_password(self) -> str:
        self._check_users()
        user_password = (
            application_settings.REDHAT_PASSWORD
            or application_settings.SUBSCRIPTIONS_PASSWORD
        )

        return user_password

    def _get_http_request_headers(self) -> dict:
        return {
            "Content-Type": self.PAYLOAD_CONTENT_TYPE,
            "User-Agent": "EDA-metrics-agent",
        }

    def _check_users(self) -> None:
        if (
            application_settings.REDHAT_USERNAME
            and application_settings.REDHAT_PASSWORD
        ):
            return

        if (
            application_settings.SUBSCRIPTIONS_USERNAME
            and application_settings.SUBSCRIPTIONS_PASSWORD
        ):
            return

        raise MissingUserPasswordError(
            "User information is missing in application settings"
        )
