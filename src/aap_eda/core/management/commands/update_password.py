#  Copyright 2023 Red Hat, Inc.
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
    help = "Update user password."

    def add_arguments(self, parser):
        parser.add_argument("-u", "--username", required=True)
        parser.add_argument("-p", "--password", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        try:
            user = models.User.objects.get(username=username)
            user.set_password(password)
            user.save()
        except models.User.DoesNotExist:
            raise CommandError(f"User '{username}' does not exist.")

        self.stdout.write(
            f"Successfully updated the password of user '{username}'"
        )
