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

import pytest
from rest_framework.test import APIClient

from aap_eda.core import models

ADMIN_USERNAME = "test.admin"
ADMIN_PASSWORD = "test.admin.123"


@pytest.fixture
def admin_user():
    return models.User.objects.create(
        username=ADMIN_USERNAME,
        password=ADMIN_PASSWORD,
        email="admin@localhost",
        is_superuser=True,
    )


@pytest.fixture
def client(admin_user) -> APIClient:
    """Override pytest-django client fixture.

    Return an instance of ``rest_framework.test.APIClient`` class
    instead of base ``django.test.Client`` class.
    """
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client
