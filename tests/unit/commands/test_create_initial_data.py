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

import tempfile
from unittest import mock

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import override_settings

from ansible_base.rbac.models import RoleDefinition

from aap_eda.core import models


@pytest.mark.django_db
def test_create_initial_data_postgres_cred():
    call_command("create_initial_data")
    cred = models.EdaCredential.objects.get(
        name=settings.DEFAULT_SYSTEM_PG_NOTIFY_CREDENTIAL_NAME
    )
    assert cred


@pytest.mark.django_db
def test_create_initial_data_postgres_cred_with_cert():
    pgsslkey_file = tempfile.NamedTemporaryFile()
    with open(pgsslkey_file.name, "w") as f:
        f.write("Testing")

    pgsslcert_file = tempfile.NamedTemporaryFile()
    with open(pgsslcert_file.name, "w") as f:
        f.write("Testing")

    pgsslrootcert_file = tempfile.NamedTemporaryFile()
    with open(pgsslrootcert_file.name, "w") as f:
        f.write("Testing")

    value = settings.DATABASES
    value["default"]["OPTIONS"]["sslkey"] = pgsslkey_file.name
    value["default"]["OPTIONS"]["sslcert"] = pgsslcert_file.name
    value["default"]["OPTIONS"]["sslrootcert"] = pgsslrootcert_file.name

    with override_settings(DATABASES=value):
        call_command("create_initial_data")
        cred = models.EdaCredential.objects.get(
            name=settings.DEFAULT_SYSTEM_PG_NOTIFY_CREDENTIAL_NAME
        )
        assert cred


@pytest.mark.django_db
def test_create_initial_data_postgres_cred_with_missing_cert():
    missing_file = "/should_not_exist/_should_not_exist_pg_file_"
    value = settings.DATABASES
    value["default"]["OPTIONS"]["sslkey"] = missing_file
    value["default"]["OPTIONS"]["sslcert"] = missing_file
    value["default"]["OPTIONS"]["sslrootcert"] = missing_file

    with override_settings(DATABASES=value):
        with pytest.raises(ImproperlyConfigured):
            call_command("create_initial_data")


@pytest.mark.django_db
def test_project_level_role_rename():
    with mock.patch('aap_eda.core.management.commands.create_initial_data.Command._update_postgres_credentials'):
        call_command("create_initial_data")
        assert RoleDefinition.objects.count() > 5  # sanity
        assert not RoleDefinition.objects.filter(name="Project Admin").exists()
        assert not RoleDefinition.objects.filter(name="Project Use").exists()
