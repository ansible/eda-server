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
import secrets

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import enums, models
from tests.integration.constants import api_url_v1


@pytest.mark.parametrize(
    ("input_field_name", "metadata", "status_code"),
    [
        (
            "password",
            {
                "secret_path": "secret/foo",
                "secret_key": "bar",
            },
            status.HTTP_201_CREATED,
        ),
        (
            "does_not_exist",
            {
                "secret_path": "secret/foo",
                "secret_key": "bar",
            },
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "password",
            {
                "secret_path_missing": "secret/foo",
                "secret_key": "bar",
            },
            status.HTTP_400_BAD_REQUEST,
        ),
    ],
)
@pytest.mark.django_db
def test_create_credential_input_source(
    admin_client: APIClient,
    default_organization: models.Organization,
    preseed_credential_types,
    input_field_name: str,
    metadata: dict,
    status_code,
):
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
        f"{api_url_v1}/eda-credentials/", data=data_in
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
            "token": "token1",
        },
        "credential_type_id": hashi_type.id,
        "organization_id": default_organization.id,
    }
    response = admin_client.post(
        f"{api_url_v1}/eda-credentials/", data=data_in
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
        f"{api_url_v1}/credential-input-sources/", data=data_in
    )
    assert response.status_code == status_code


@pytest.mark.parametrize(
    ("updated_metadata", "status_code"),
    [
        (
            {
                "secret_path": "secret/foo",
                "secret_key": "baz",
            },
            status.HTTP_200_OK,
        ),
        (
            {
                "missing_1": "secret/foo",
            },
            status.HTTP_400_BAD_REQUEST,
        ),
    ],
)
@pytest.mark.django_db
def test_update_credential_input_source(
    admin_client: APIClient,
    default_organization: models.Organization,
    preseed_credential_types,
    default_credential_input_source: models.CredentialInputSource,
    updated_metadata: dict,
    status_code,
):
    data_in = {
        "metadata": updated_metadata,
    }
    response = admin_client.patch(
        (
            f"{api_url_v1}/credential-input-sources/"
            f"{default_credential_input_source.id}/"
        ),
        data=data_in,
    )
    assert response.status_code == status_code


@pytest.mark.django_db
def test_delete_credential_input_source(
    admin_client: APIClient,
    default_organization: models.Organization,
    preseed_credential_types,
    default_credential_input_source: models.CredentialInputSource,
):
    response = admin_client.delete(
        (
            f"{api_url_v1}/credential-input-sources/"
            f"{default_credential_input_source.id}/"
        ),
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_list_credential_input_source(
    admin_client: APIClient,
    default_organization: models.Organization,
    preseed_credential_types,
    default_credential_input_source: models.CredentialInputSource,
):
    response = admin_client.get(
        (f"{api_url_v1}/credential-input-sources/"),
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1


@pytest.mark.django_db
def test_get_credential_input_source(
    admin_client: APIClient,
    default_organization: models.Organization,
    preseed_credential_types,
    default_credential_input_source: models.CredentialInputSource,
):
    response = admin_client.get(
        (
            f"{api_url_v1}/credential-input-sources/"
            f"{default_credential_input_source.id}/"
        ),
    )
    assert response.status_code == status.HTTP_200_OK
    credential_input_source = response.json()
    assert credential_input_source["id"] == default_credential_input_source.id
