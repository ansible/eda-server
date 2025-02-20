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
import json
import logging
from datetime import datetime
from typing import Optional

from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from flags.state import flag_enabled
from insights_analytics_collector import Collector

from aap_eda.analytics import analytics_collectors, package, utils
from aap_eda.conf.settings import application_settings


class AnalyticsCollector(Collector):
    @staticmethod
    def db_connection() -> connection:
        return connection

    @staticmethod
    def _package_class() -> package.Package:
        return package.Package

    def _is_shipping_configured(self) -> bool:
        if not application_settings.INSIGHTS_TRACKING_STATE:
            self.logger.warning(
                "Insights for Event Driven Ansible is not enabled."
            )
            return False

        return True

    def _is_valid_license(self) -> bool:
        # ignore license information checking for now
        return True

    def _last_gathering(self) -> Optional[datetime]:
        last_gather = application_settings.AUTOMATION_ANALYTICS_LAST_GATHER
        if not last_gather:
            return None

        self.logger.info(f"Last gather: {last_gather}")
        return datetime.fromisoformat(last_gather)

    def _load_last_gathered_entries(self) -> dict:
        try:
            last_entries = (
                application_settings.AUTOMATION_ANALYTICS_LAST_ENTRIES
            )
            last_entries = last_entries.replace("'", '"')
            self.logger.info(f"Last collect entries: {last_entries}")

            return json.loads(last_entries, object_hook=utils.datetime_hook)
        except (json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Failed to load last entries: {str(e)}")
            return {}

    def _save_last_gathered_entries(self, last_gathered_entries: dict) -> None:
        application_settings.AUTOMATION_ANALYTICS_LAST_ENTRIES = json.dumps(
            last_gathered_entries, cls=DjangoJSONEncoder
        )
        self.logger.info(
            "Save last_entries: "
            f"{application_settings.AUTOMATION_ANALYTICS_LAST_ENTRIES}"
        )

    def _save_last_gather(self) -> None:
        self.logger.info(f"Save last_gather: {self.gather_until}")

        application_settings.AUTOMATION_ANALYTICS_LAST_GATHER = (
            self.gather_until.isoformat()
        )


def gather(collection_type="scheduled", since=None, until=None, logger=None):
    if not logger:
        logger = logging.getLogger("aap_eda.analytics")
    if not flag_enabled("FEATURE_EDA_ANALYTICS_ENABLED"):
        logger.info("FEATURE_EDA_ANALYTICS_ENABLED is set to False.")
        return
    collector = AnalyticsCollector(
        collector_module=analytics_collectors,
        collection_type=collection_type,
        logger=logger,
    )
    return collector.gather(since=since, until=until)
