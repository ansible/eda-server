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
import os
from datetime import datetime

from django.core.management.base import BaseCommand

try:
    from ansible_base.authentication.models import Authenticator
except ImportError:
    raise ImportError(
        "The 'ansible_base' module or its models could not be imported."
    )


class Command(BaseCommand):
    help = "Dump auth config data from database to a JSON file"

    def add_arguments(self, parser):
        parser.add_argument(
            "output_file",
            nargs="?",
            type=str,
            default="auth_config.json",
            help="Output JSON file path",
        )

    def handle(self, *args, **options):
        try:
            # Retrieve data from the database
            queryset = Authenticator.objects.all()

            # Limit the data to certain columns only
            queryset = queryset.values("type", "configuration")

            # Convert queryset to a list of dictionaries
            data = list(queryset)

            # Convert datetime objects to strings
            for item in data:
                for key, value in item.items():
                    if isinstance(value, datetime):
                        item[key] = value.strftime("%Y-%m-%d %H:%M:%S")

            # Define the path for the output JSON file
            output_file = options["output_file"]

            # Ensure the directory exists
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            # Write data to the JSON file
            with open(output_file, "w") as f:
                json.dump(data, f, indent=4)

            self.stdout.write(
                self.style.SUCCESS(f"Auth config data dumped to {output_file}")
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred: {str(e)}"))
