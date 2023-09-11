#  Copyright 2022 Red Hat, Inc.
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

from django.contrib.auth.models import AbstractUser
from django.db import models

from aap_eda.core.utils.crypto.fields import EncryptedTextField

from .mixins import ModifiedAtUpdaterMixin


class User(ModifiedAtUpdaterMixin, AbstractUser):
    """Custom user model.

    If you’re starting a new project, it’s highly recommended to set up a
    custom user model, even if the default User model is sufficient for you.
    This model behaves identically to the default user model,
    but you’ll be able to customize it in the future if the need arises.

    Refer to https://docs.djangoproject.com/en/4.1/topics/auth/customizing/#substituting-a-custom-user-model
    """  # noqa: E501

    roles = models.ManyToManyField("Role", related_name="users")
    modified_at = models.DateTimeField(auto_now=True, null=False)


class AwxToken(ModifiedAtUpdaterMixin, models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    name = models.TextField(null=False, blank=False)
    description = models.TextField(null=False, blank=True, default="")
    token = EncryptedTextField(null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)

    class Meta:
        unique_together = ["user", "name"]
