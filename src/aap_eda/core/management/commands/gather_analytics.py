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
from datetime import timezone

from dateutil import parser
from django.core.management.base import BaseCommand, CommandParser
from flags.state import flag_enabled

from aap_eda.analytics import collector


class Command(BaseCommand):
    """Collect analytics data."""

    help = "Collect analytics data"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            dest="dry-run",
            action="store_true",
            help=(
                "Gather analytics without shipping. Works even if analytics"
                " are disabled in settings."
            ),
        )
        parser.add_argument(
            "--ship",
            dest="ship",
            action="store_true",
            help="Enable to ship metrics to the Red Hat Cloud",
        )
        parser.add_argument(
            "--since",
            dest="since",
            action="store",
            help="Start date for collection",
        )
        parser.add_argument(
            "--until",
            dest="until",
            action="store",
            help="End date for collection",
        )

    def init_logging(self) -> None:
        self.logger = logging.getLogger("aap_eda.analytics")
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(handler)
        self.logger.propagate = False

    def handle(self, *args, **options):
        self.init_logging()
        opt_ship = options.get("ship")
        opt_dry_run = options.get("dry-run")
        opt_since = options.get("since")
        opt_until = options.get("until")

        if not flag_enabled("FEATURE_EDA_ANALYTICS_ENABLED"):
            self.logger.error("FEATURE_EDA_ANALYTICS_ENABLED is set to False.")
            return

        since = parser.parse(opt_since) if opt_since else None
        if since and since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        until = parser.parse(opt_until) if opt_until else None
        if until and until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)

        if opt_ship and opt_dry_run:
            self.logger.error(
                "Both --ship and --dry-run cannot be processed "
                "at the same time."
            )
            return

        if not opt_ship and not opt_dry_run:
            self.logger.error("Either --ship or --dry-run needs to be set.")
            return

        collection_type = "manual" if opt_ship else "dry-run"
        tgzfiles = collector.gather(
            collection_type=collection_type,
            since=since,
            until=until,
            logger=self.logger,
        )

        if not tgzfiles:
            self.logger.info("No analytics collected")
            return

        for tgz in tgzfiles:
            self.logger.info(tgz)

        self.logger.info("Analytics collection is done")
