"""Test external Secret Management System."""

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
import json
import secrets
from unittest import mock

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import enums, models
from aap_eda.core.exceptions import CredentialPluginError
from aap_eda.core.utils.external_sms import get_external_secrets
from tests.integration.constants import api_url_v1


@pytest.mark.parametrize(
    ("input_field_name", "metadata", "raise_exception"),
    [
        (
            "password",
            {
                "secret_path": "secret/foo",
                "secret_key": "bar",
            },
            False,
        ),
        (
            "password",
            {
                "secret_path": "secret/foo",
                "secret_key": "bar",
            },
            True,
        ),
    ],
)
@pytest.mark.django_db
def test_get_external_secrets(
    admin_client: APIClient,
    default_organization: models.Organization,
    preseed_credential_types,
    input_field_name: str,
    metadata: dict,
    raise_exception: bool,
):
    """Test getting external secrets."""
    reg_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    data_in = {
        "name": "eda-credential-1",
        "inputs": {
            "host": "quay.io",
            "username": "fred",
            "password": secrets.token_hex(32),
        },
        "credential_type_id": reg_type.id,
        "organization_id": default_organization.id,
    }

    response = admin_client.post(
        f"{api_url_v1}/eda-credentials/",
        data=json.dumps(data_in),
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    target_credential = response.json()
    hashi_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.HASHICORP_LOOKUP
    )

    data_in = {
        "name": "eda-credential-2",
        "inputs": {
            "url": "https://www.example.com",
            "api_version": "v2",
            "token": secrets.token_hex(32),
        },
        "credential_type_id": hashi_type.id,
        "organization_id": default_organization.id,
    }
    response = admin_client.post(
        f"{api_url_v1}/eda-credentials/",
        data=json.dumps(data_in),
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    source_credential = response.json()

    data_in = {
        "source_credential": source_credential["id"],
        "target_credential": target_credential["id"],
        "input_field_name": input_field_name,
        "organization_id": default_organization.id,
        "metadata": metadata,
    }
    response = admin_client.post(
        f"{api_url_v1}/credential-input-sources/",
        data=json.dumps(data_in),
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_201_CREATED

    if raise_exception:
        with mock.patch(
            "aap_eda.core.utils.external_sms.run_plugin",
            side_effect=CredentialPluginError("Kaboom"),
        ):
            with pytest.raises(CredentialPluginError):
                get_external_secrets(target_credential["id"])
    else:
        with mock.patch(
            "aap_eda.core.utils.external_sms.run_plugin", return_value="abc"
        ):
            result = get_external_secrets(target_credential["id"])
            assert result[input_field_name] == "abc"
