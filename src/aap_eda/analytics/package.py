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


class Package(InsightsAnalyticsPackage):
    PAYLOAD_CONTENT_TYPE = "application/vnd.redhat.aap-eda.filename+tgz"
    CERT_PATH = settings.INSIGHTS_CERT_PATH

    def _tarname_base(self):
        timestamp = self.collector.gather_until
        return f'eda-analytics-{timestamp.strftime("%Y-%m-%d-%H%M%S%z")}'

    def get_ingress_url(self):
        return application_settings.AUTOMATION_ANALYTICS_URL

    def shipping_auth_mode(self):
        return settings.AUTOMATION_AUTH_METHOD

    def _get_rh_user(self):
        return application_settings.REDHAT_USERNAME

    def _get_rh_password(self):
        return application_settings.REDHAT_PASSWORD

    def _get_http_request_headers(self):
        return {
            "Content-Type": self.PAYLOAD_CONTENT_TYPE,
            "User-Agent": "EDA-metrics-agent",
        }
