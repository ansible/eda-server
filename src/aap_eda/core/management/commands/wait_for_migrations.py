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
import time

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = "Wait for all migrations to be applied within a timeout period."

    def add_arguments(self, parser):
        parser.add_argument(
            "-t",
            "--timeout",
            type=int,
            default=10,
            help=(
                "Time in seconds to wait for migrations to be applied "
                "(default is 10 seconds)."
            ),
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]
        start_time = time.time()
        elapsed_time = 0

        while elapsed_time < timeout:
            if not self.migrations_pending():
                self.stdout.write(
                    self.style.SUCCESS("All migrations are applied.")
                )
                return
            time.sleep(1)
            elapsed_time = time.time() - start_time

        self.stderr.write(
            self.style.ERROR("Timeout exceeded. There are pending migrations.")
        )
        raise SystemExit(1)

    def migrations_pending(self) -> bool:
        """Check if there are pending migrations."""
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        plan = executor.migration_plan(targets)
        return bool(plan)
