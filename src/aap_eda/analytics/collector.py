import json

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from insights_analytics_collector import Collector

from aap_eda.analytics.package import Package
from aap_eda.analytics.utils import datetime_hook


class AnalyticsCollector(Collector):
    @staticmethod
    def db_connection():
        return connection

    @staticmethod
    def _package_class():
        return Package

    def get_last_gathering(self):
        return self._last_gathering()

    def _is_shipping_configured(self):
        if not settings.INSIGHTS_TRACKING_STATE:
            self.logger.warning(
                "Insights for Event Driven Ansible is not enabled."
            )
            return False

        return True

    def _is_valid_license(self):
        # ignore license information checking for now
        return True

    def _last_gathering(self):
        return settings.AUTOMATION_ANALYTICS_LAST_GATHER

    def _load_last_gathered_entries(self):
        last_entries = settings.AUTOMATION_ANALYTICS_LAST_ENTRIES

        return json.loads(
            last_entries.value
            if last_entries and last_entries.value
            else "{}",  # noqa: P103
            object_hook=datetime_hook,
        )

    def _save_last_gathered_entries(self, last_gathered_entries):
        self.logger.info(f"Save last_entries: {last_gathered_entries}")

        settings.AUTOMATION_ANALYTICS_LAST_ENTRIES = json.dumps(
            last_gathered_entries, cls=DjangoJSONEncoder
        )

    def _save_last_gather(self):
        self.logger.info(f"Save last_gather: {self.gather_until}")

        settings.AUTOMATION_ANALYTICS_LAST_GATHER = self.gather_until
