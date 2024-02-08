from ansible_base.lib.abstract_models.organization import AbstractOrganization
from django.conf import settings
from django.db import models


class OrganizationManager(models.Manager):
    def get_default(self):
        return self.get(name=settings.DEFAULT_ORGANIZATION_NAME)


class Organization(AbstractOrganization):
    objects = OrganizationManager()
