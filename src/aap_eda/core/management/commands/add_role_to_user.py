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
    help = "Add one or multiple roles to a user."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("roles", nargs="+", metavar="role")

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"]
        try:
            user = models.User.objects.get(username=username)
        except models.User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist. ')

        role_names = options["roles"]
        for role_name in role_names:
            try:
                role = models.Role.objects.get(name=role_name)
            except models.Role.DoesNotExist:
                raise CommandError(f'Role "{role_name} does not exist."')
            user.roles.add(role)
        self.stdout.write(
            'Successfully added roles "{0}" to user "{1}"'.format(
                ", ".join(role_names),
                username,
            )
        )
