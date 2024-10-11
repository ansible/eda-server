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

from typing import List, Union

import pytest
from django.core.management import call_command

from aap_eda.core import enums, models
from aap_eda.core.management.commands.create_initial_data import (
    NEW_HELP_TEXT,
    ORIG_HELP_TEXT,
)

INPUTS = {
    "fields": [
        {
            "id": "host",
            "label": "Red Hat Ansible Automation Platform",
            "type": "string",
            "help_text": ORIG_HELP_TEXT,
        },
        {
            "id": "username",
            "label": "Username",
            "type": "string",
            "help_text": (
                "Red Hat Ansible Automation Platform username id"
                " to authenticate as.This should not be set if"
                " an OAuth token is being used."
            ),
        },
        {
            "id": "password",
            "label": "Password",
            "type": "string",
            "secret": True,
        },
        {
            "id": "oauth_token",
            "label": "OAuth Token",
            "type": "string",
            "secret": True,
            "help_text": (
                "An OAuth token to use to authenticate with."
                "This should not be set if username/password"
                " are being used."
            ),
        },
        {
            "id": "verify_ssl",
            "label": "Verify SSL",
            "type": "boolean",
            "secret": False,
        },
    ],
    "required": ["host"],
}

INJECTORS = {
    "env": {
        "TOWER_HOST": "{{host}}",
        "TOWER_USERNAME": "{{username}}",
        "TOWER_PASSWORD": "{{password}}",
        "TOWER_VERIFY_SSL": "{{verify_ssl}}",
        "TOWER_OAUTH_TOKEN": "{{oauth_token}}",
        "CONTROLLER_HOST": "{{host}}",
        "CONTROLLER_USERNAME": "{{username}}",
        "CONTROLLER_PASSWORD": "{{password}}",
        "CONTROLLER_VERIFY_SSL": "{{verify_ssl}}",
        "CONTROLLER_OAUTH_TOKEN": "{{oauth_token}}",
    }
}


@pytest.fixture
def rollback_migration():
    call_command("migrate", "core", "0050")
    yield
    call_command("migrate")


@pytest.mark.django_db
def test_migration(rollback_migration):
    credential_type = _prepare_aap_credetial_type()

    call_command("migrate", "core", "0051")
    credential_type.refresh_from_db()
    assert _get_help_text(credential_type) == list(NEW_HELP_TEXT)


def _get_help_text(
    credential_type: models.CredentialType,
) -> Union[str, List[str]]:
    for field in credential_type.inputs["fields"]:
        if field["id"] == "host":
            return field["help_text"]


def _prepare_aap_credetial_type() -> models.CredentialType:
    return models.CredentialType.objects.create(
        name=enums.DefaultCredentialType.AAP,
        inputs=INPUTS,
        injectors=INJECTORS,
    )
