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


from unittest import mock

import pytest
from django.apps import apps
from django.conf import settings

from aap_eda.core import models


@pytest.mark.django_db
def test_startup_encryption_check_good_key():
    models.Credential.objects.create(
        name="test-credential",
        username="Rick Sanchez",
        secret="Wubba Lubba Dub Dub",
    )
    api_config = apps.get_app_config("api")

    assert api_config.ready() is None


@pytest.mark.django_db
def test_startup_encryption_check_bad_key():
    models.Credential.objects.create(
        name="test-credential",
        username="Rick Sanchez",
        secret="Wubba Lubba Dub Dub",
    )
    api_config = apps.get_app_config("api")
    with mock.patch.object(
        settings, "SECRET_KEY", new="bad_key"
    ), pytest.raises(RuntimeError):
        api_config.ready()


@pytest.mark.django_db
def test_startup_encryption_check_no_records():
    api_config = apps.get_app_config("api")

    assert api_config.ready() is None
