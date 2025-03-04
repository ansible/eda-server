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

from aap_eda.analytics import utils
from aap_eda.analytics.utils import ServiceToken
from aap_eda.utils import get_eda_version


class FailedToUploadPayload(Exception):
    """Raised when required user credentials are missing."""

    pass


class Package(InsightsAnalyticsPackage):
    """Handles packaging and shipping analytics data to Red Hat services.

    Attributes:
        PAYLOAD_CONTENT_TYPE: MIME type for the analytics payload
        USER_AGENT: Identifier for the analytics client
    """

    PAYLOAD_CONTENT_TYPE = (
        "application/vnd.redhat.aap-event-driven-ansible.filename+tgz"
    )
    USER_AGENT = "EDA-metrics-agent"
    CERT_PATH = settings.INSIGHTS_CERT_PATH
    SHIPPING_AUTH_SERVICE_ACCOUNT = "service-account"

    token = ServiceToken()

    def _tarname_base(self) -> str:
        timestamp = self.collector.gather_until
        return f'eda-analytics-{timestamp.strftime("%Y-%m-%d-%H%M%S%z")}'

    def get_ingress_url(self) -> str:
        return utils.get_analytics_url()

    def shipping_auth_mode(self) -> str:
        return utils.get_auth_mode()

    def _get_rh_user(self) -> str:
        return utils.get_username()

    def _get_rh_password(self) -> str:
        return utils.get_password()

    def _get_http_request_headers(self) -> dict:
        return {
            "Content-Type": self.PAYLOAD_CONTENT_TYPE,
            "User-Agent": self.USER_AGENT,
            "X-EDA-Version": get_eda_version(),
        }

    def _send_data(self, url, files, session):
        if self.shipping_auth_mode() == self.SHIPPING_AUTH_SERVICE_ACCOUNT:
            self.logger.info(
                f"AUTH_MODE: {self.SHIPPING_AUTH_SERVICE_ACCOUNT}"
            )
            if self.token.is_expired():
                self.token = utils.generate_token()

            headers = session.headers
            headers["authorization"] = f"Bearer {self.token.access_token}"

            proxies = {}
            if utils.get_proxy_url():
                proxies = {"https": utils.get_proxy_url()}

            response = session.post(
                url,
                files=files,
                verify=utils.get_cert_path(),
                proxies=proxies,
                headers=headers,
                timeout=(31, 31),
            )

        elif self.shipping_auth_mode() == self.SHIPPING_AUTH_USERPASS:
            self.logger.info(f"AUTH_MODE: {self.SHIPPING_AUTH_USERPASS}")
            response = session.post(
                url,
                files=files,
                verify=utils.get_cert_path(),
                auth=(self._get_rh_user(), self._get_rh_password()),
                headers=session.headers,
                timeout=(31, 31),
            )

        else:
            self.logger.info(f"AUTH_MODE: {self.shipping_auth_mode()}")
            response = session.post(
                url, files=files, headers=session.headers, timeout=(31, 31)
            )

        if response.status_code >= 300:
            raise FailedToUploadPayload(
                f"Upload failed with status {response.status_code}, "
                f"{response.text}"
            )

        return True
