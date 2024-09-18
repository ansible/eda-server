import logging

from django.conf import settings
from insights_analytics_collector import Package as InsightsAnalyticsPackage

logger = logging.getLogger(__name__)


class Package(InsightsAnalyticsPackage):
    PAYLOAD_CONTENT_TYPE = "application/vnd.redhat.aap-eda.filename+tgz"
    CERT_PATH = settings.INSIGHTS_CERT_PATH

    def _tarname_base(self):
        timestamp = self.collector.gather_until
        return f'eda-analytics-{timestamp.strftime("%Y-%m-%d-%H%M%S%z")}'

    def get_ingress_url(self):
        return settings.AUTOMATION_ANALYTICS_URL

    def shipping_auth_mode(self):
        return settings.AUTOMATION_AUTH_METHOD

    def _get_rh_user(self):
        return settings.REDHAT_USERNAME

    def _get_rh_password(self):
        return settings.REDHAT_PASSWORD

    def _get_http_request_headers(self):
        return {
            "Content-Type": self.PAYLOAD_CONTENT_TYPE,
            "User-Agent": "EDA-metrics-agent",
        }
