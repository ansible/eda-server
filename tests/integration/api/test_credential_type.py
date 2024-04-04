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
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.constants import api_url_v1

INPUT = {
    "fields": [
        {
            "id": "host",
            "label": "Authentication URL",
            "type": "string",
            "help_text": (
                "Authentication endpoint for the container registry."
            ),
            "default": "quay.io",
        },
        {"id": "username", "label": "Username", "type": "string"},
        {
            "id": "password",
            "label": "Password or Token",
            "type": "string",
            "secret": True,
            "help_text": ("A password or token used to authenticate with"),
        },
        {
            "id": "verify_ssl",
            "label": "Verify SSL",
            "type": "boolean",
            "default": True,
        },
    ],
    "required": ["host"],
}


@pytest.mark.django_db
def test_create_credential_type(client: APIClient):
    injectors = {
        "extra_vars": {
            "host": "localhost",
            "username": "adam",
            "password": "password",
            "verify_ssl": False,
        }
    }
    data_in = {
        "name": "credential_type_1",
        "description": "desc here",
        "inputs": INPUT,
        "injectors": injectors,
    }

    response = client.post(f"{api_url_v1}/credential-types/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "credential_type_1"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("inputs", "injectors", "status_code", "error_message"),
    [
        (
            {"a": "b"},
            {"a": "b"},
            status.HTTP_400_BAD_REQUEST,
            "'fields' must exist and non empty",
        ),
        (
            {"fields": {"id": "username"}},
            {"username": "fred"},
            status.HTTP_400_BAD_REQUEST,
            "'fields' must be a list",
        ),
        (
            {"fields": [{"id": "username"}]},
            {"username": "fred"},
            status.HTTP_400_BAD_REQUEST,
            "label must exist and be a string",
        ),
    ],
)
def test_create_credential_type_with_schema_validate_errors(
    client: APIClient, inputs, injectors, status_code, error_message
):
    data_in = {
        "name": "credential_type_1",
        "description": "desc here",
        "inputs": inputs,
        "injectors": injectors,
    }

    response = client.post(f"{api_url_v1}/credential-types/", data=data_in)
    assert response.status_code == status_code
    assert error_message in response.data["inputs"]


@pytest.mark.django_db
def test_retrieve_credential_type(client: APIClient):
    obj = models.CredentialType.objects.create(
        name="type1", inputs={"fields": [{"a": "b"}]}, injectors={}
    )
    response = client.get(f"{api_url_v1}/credential-types/{obj.id}/")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_list_credential_types(client: APIClient):
    objects = models.CredentialType.objects.bulk_create(
        [
            models.CredentialType(
                name="type1", inputs={"fields": [{"a": "b"}]}, injectors={}
            ),
            models.CredentialType(
                name="type2", inputs={"fields": [{"1": "2"}]}, injectors={}
            ),
        ]
    )
    response = client.get(f"{api_url_v1}/credential-types/")
    assert response.status_code == status.HTTP_200_OK
    assert len(objects) == 2


@pytest.mark.django_db
def test_delete_managed_credential_type(client: APIClient):
    obj = models.CredentialType.objects.create(
        name="type1",
        inputs={"fields": [{"a": "b"}]},
        injectors={},
        managed=True,
    )
    response = client.delete(f"{api_url_v1}/credential-types/{obj.id}/")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_delete_credential_type(client: APIClient):
    obj = models.CredentialType.objects.create(
        name="type1",
        inputs={"fields": [{"a": "b"}]},
        injectors={},
        managed=False,
    )
    response = client.delete(f"{api_url_v1}/credential-types/{obj.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("old_inputs", "new_inputs", "status_code", "passed", "message"),
    [
        (
            {"a": "b"},
            {"c": "d"},
            status.HTTP_400_BAD_REQUEST,
            False,
            "'fields' must exist and non empty",
        ),
        (
            {"username": "fred"},
            {"fields": [{"id": "username", "label": "Username"}]},
            status.HTTP_200_OK,
            True,
            {"id": "username", "label": "Username"},
        ),
    ],
)
def test_partial_update_inputs_credential_type(
    client: APIClient, old_inputs, new_inputs, status_code, passed, message
):
    obj = models.CredentialType.objects.create(
        name="type",
        inputs=old_inputs,
        injectors={},
        managed=False,
    )
    data = {"inputs": new_inputs}
    response = client.patch(
        f"{api_url_v1}/credential-types/{obj.id}/", data=data
    )
    assert response.status_code == status_code

    if passed:
        obj.refresh_from_db()
        assert obj.inputs == new_inputs
    else:
        assert message in response.data["inputs"]
