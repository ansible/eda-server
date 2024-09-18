import json
from datetime import datetime

from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from insights_analytics_collector import Collector

from aap_eda.analytics.package import Package
from aap_eda.analytics.utils import datetime_hook
from aap_eda.conf.settings import application_settings


class AnalyticsCollector(Collector):
    @staticmethod
    def db_connection():
        return connection

    @staticmethod
    def _package_class():
        return Package

    def _is_shipping_configured(self):
        if not application_settings.INSIGHTS_TRACKING_STATE:
            self.logger.warning(
                "Insights for Event Driven Ansible is not enabled."
            )
            return False

        return True

    def _is_valid_license(self):
        # ignore license information checking for now
        return True

    def _last_gathering(self):
        self.logger.info(
            "Last gather: "
            f"{application_settings.AUTOMATION_ANALYTICS_LAST_GATHER}"
        )

        return (
            datetime.fromisoformat(
                application_settings.AUTOMATION_ANALYTICS_LAST_GATHER
            )
            if bool(application_settings.AUTOMATION_ANALYTICS_LAST_GATHER)
            else None
        )

    def _load_last_gathered_entries(self):
        last_entries = application_settings.AUTOMATION_ANALYTICS_LAST_ENTRIES
        last_entries = last_entries.replace("'", '"')
        self.logger.info(f"Last collect entries: {last_entries}")

        return json.loads(last_entries, object_hook=datetime_hook)

    def _save_last_gathered_entries(self, last_gathered_entries):
        application_settings.AUTOMATION_ANALYTICS_LAST_ENTRIES = json.dumps(
            last_gathered_entries, cls=DjangoJSONEncoder
        )
        self.logger.info(
            "Save last_entries: "
            f"{application_settings.AUTOMATION_ANALYTICS_LAST_ENTRIES}"
        )

    def _save_last_gather(self):
        self.logger.info(f"Save last_gather: {self.gather_until}")

        application_settings.AUTOMATION_ANALYTICS_LAST_GATHER = (
            self.gather_until.isoformat()
        )
