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

from ansible_base.lib.abstract_models.organization import AbstractOrganization
from ansible_base.resource_registry.fields import AnsibleResourceField
from django.conf import settings
from django.db import models


class OrganizationManager(models.Manager):
    def get_default(self):
        return self.get(name=settings.DEFAULT_ORGANIZATION_NAME)


class Organization(AbstractOrganization):
    objects = OrganizationManager()

    resource = AnsibleResourceField(primary_key_field="id")

    class Meta:
        app_label = "core"
        permissions = [
            (
                "member_organization",
                "Basic participation permissions for organization",
            ),
        ]
        default_permissions = (
            "change",
            "delete",
            "view",
        )  # add permission pending system roles
