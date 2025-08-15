#  Copyright 2025 Red Hat, Inc.
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
from django.core.management import BaseCommand, CommandError
from django.db import transaction

from aap_eda.core import models


class Command(BaseCommand):
    help = "Fix project import state and error message in the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "-n", "--name", required=True, help="Name of the project to update"
        )
        parser.add_argument(
            "-s",
            "--state",
            required=True,
            choices=["failed", "completed"],
            help="New import state for the project",
        )
        parser.add_argument(
            "-e",
            "--error",
            required=False,
            help="Import error message (optional)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        project_name = options["name"]
        import_state = options["state"]
        import_error = options.get("error")

        try:
            project = models.Project.objects.get(name=project_name)
        except models.Project.DoesNotExist:
            raise CommandError(f"Project '{project_name}' does not exist.")

        # Store old values for logging
        old_state = project.import_state
        old_error = project.import_error

        # Update the project
        project.import_state = import_state
        if import_error is not None:
            project.import_error = import_error
        elif import_state == "completed":
            # Clear import_error when state is completed and no error is
            # explicitly provided
            project.import_error = None
        project.save(
            update_fields=["import_state", "import_error", "modified_at"]
        )

        # Log the changes
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated project '{project_name}'"
            )
        )
        self.stdout.write(f"  Import state: {old_state} -> {import_state}")
        if import_error is not None:
            self.stdout.write(f"  Import error: {old_error} -> {import_error}")
        elif import_state == "completed" and old_error is not None:
            self.stdout.write(f"  Import error: {old_error} -> (cleared)")
        elif old_error is not None:
            self.stdout.write(f"  Import error: {old_error} -> (unchanged)")
