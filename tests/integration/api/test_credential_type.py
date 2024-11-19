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
from typing import Optional

import pytest
from pytest_lazyfixture import lazy_fixture
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import enums, models
from aap_eda.core.utils.credentials import SUPPORTED_KEYS_IN_INJECTORS
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

INPUT_SANS_TYPE = {
    "fields": [
        {
            "id": "host",
            "label": "Authentication URL",
            "help_text": (
                "Authentication endpoint for the container registry."
            ),
            "default": "quay.io",
        },
        {"id": "username", "label": "Username", "type": "string"},
        {
            "id": "password",
            "label": "Password or Token",
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
@pytest.mark.parametrize(
    ("inputs", "injectors"),
    [
        (
            {},
            {},
        ),
        (
            INPUT,
            {},
        ),
        (
            {},
            {
                "extra_vars": {
                    "host": "localhost",
                    "username": "adam",
                    "password": "password",
                    "verify_ssl": False,
                }
            },
        ),
    ],
)
def test_create_credential_type(
    superuser_client: APIClient, inputs, injectors
):
    data_in = {
        "name": "credential_type_1",
        "description": "desc here",
        "inputs": inputs,
        "injectors": injectors,
    }

    response = superuser_client.post(
        f"{api_url_v1}/credential-types/", data=data_in
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "credential_type_1"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client", "expected_code"),
    [
        pytest.param(
            lazy_fixture("admin_client"),
            status.HTTP_403_FORBIDDEN,
            id="org_admin",
        ),
        pytest.param(
            lazy_fixture("base_client"),
            status.HTTP_401_UNAUTHORIZED,
            id="no_authenticated",
        ),
    ],
)
def test_create_credential_type_no_superuser(
    client: APIClient, expected_code: int
):
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
    assert response.status_code == expected_code


@pytest.mark.django_db
def test_create_credential_type_sans_type(superuser_client: APIClient):
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
        "inputs": INPUT_SANS_TYPE,
        "injectors": injectors,
    }

    response = superuser_client.post(
        f"{api_url_v1}/credential-types/", data=data_in
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "credential_type_1"
    assert response.data["inputs"]["fields"][0]["type"] == "string"
    assert response.data["inputs"]["fields"][1]["type"] == "string"
    assert response.data["inputs"]["fields"][2]["type"] == "string"
    assert response.data["inputs"]["fields"][3]["type"] == "boolean"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("inputs", "injectors", "error_key", "error_message"),
    [
        (
            {"a": "b"},
            {"a": "b"},
            "injectors",
            "Injectors must have keys defined in "
            f"{sorted(SUPPORTED_KEYS_IN_INJECTORS)}",
        ),
        (
            {"fields": {"id": "username"}},
            {"username": "fred"},
            "inputs",
            "'fields' must be a list",
        ),
        (
            {"fields": [{"id": "username"}]},
            {"username": "fred"},
            "inputs",
            "label must exist and be a string",
        ),
        (
            {
                "fields": [
                    {
                        "id": "username",
                        "label": "Username",
                        "type": "string",
                        "default": "adam",
                    },
                ]
            },
            {
                "extra_vars": {
                    "keyfile": "{{ keyfile  }}",
                },
            },
            "injectors",
            "Injector key: keyfile has a value which refers to an undefined "
            "key error",
        ),
    ],
)
def test_create_credential_type_with_schema_validate_errors(
    superuser_client: APIClient, inputs, injectors, error_key, error_message
):
    data_in = {
        "name": "credential_type_1",
        "description": "desc here",
        "inputs": inputs,
        "injectors": injectors,
    }

    response = superuser_client.post(
        f"{api_url_v1}/credential-types/", data=data_in
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert error_message in str(response.data[error_key])


@pytest.mark.django_db
def test_retrieve_credential_type(user_client: APIClient):
    obj = models.CredentialType.objects.create(
        name="type1", inputs={"fields": [{"a": "b"}]}, injectors={}
    )
    response = user_client.get(f"{api_url_v1}/credential-types/{obj.id}/")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_retrieve_credential_type_no_auth(
    base_client: APIClient, credential_type: models.CredentialType
):
    response = base_client.get(
        f"{api_url_v1}/credential-types/{credential_type.id}/"
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_list_credential_types(superuser_client: APIClient):
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
    response = superuser_client.get(f"{api_url_v1}/credential-types/")
    assert response.status_code == status.HTTP_200_OK
    assert len(objects) == 2


@pytest.mark.django_db
def test_delete_managed_credential_type(superuser_client: APIClient):
    obj = models.CredentialType.objects.create(
        name="type1",
        inputs={"fields": [{"a": "b"}]},
        injectors={},
        managed=True,
    )
    response = superuser_client.delete(
        f"{api_url_v1}/credential-types/{obj.id}/"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_delete_credential_type(superuser_client: APIClient):
    obj = models.CredentialType.objects.create(
        name="type1",
        inputs={"fields": [{"a": "b"}]},
        injectors={},
        managed=False,
    )
    response = superuser_client.delete(
        f"{api_url_v1}/credential-types/{obj.id}/"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_delete_credential_type_with_credentials(
    superuser_client: APIClient,
    default_organization: models.Organization,
    preseed_credential_types,
):
    credential_type = models.CredentialType.objects.create(
        name="user_type",
        inputs={"fields": [{"id": "username"}]},
        injectors={},
        managed=False,
    )

    models.EdaCredential.objects.create(
        name="credential-1",
        inputs={"username": "adam"},
        credential_type=credential_type,
        organization=default_organization,
    )

    response = superuser_client.delete(
        f"{api_url_v1}/credential-types/{credential_type.id}/"
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        f"CredentialType {credential_type.name} is used by credentials"
        in response.data["errors"]
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "new_inputs",
    [{}, {"c": "d"}, {"username": "fred"}],
)
def test_partial_update_inputs_credential_type(
    superuser_client: APIClient,
    new_inputs,
):
    obj = models.CredentialType.objects.create(
        name="type",
        inputs={"fields": [{"id": "username", "label": "Username"}]},
        injectors={},
        managed=False,
    )
    data = {
        "inputs": new_inputs,
        "injectors": {"extra_vars": {"username": "Fred"}},
    }
    response = superuser_client.patch(
        f"{api_url_v1}/credential-types/{obj.id}/", data=data
    )
    assert response.status_code == status.HTTP_200_OK

    obj.refresh_from_db()
    assert obj.inputs == new_inputs


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("new_injectors", "status_code", "message"),
    [
        (
            {},
            status.HTTP_200_OK,
            None,
        ),
        (
            {"extra_vars": {"username": "Adam"}},
            status.HTTP_200_OK,
            None,
        ),
        (
            {"c": "d"},
            status.HTTP_400_BAD_REQUEST,
            (
                "Injectors must have keys defined in "
                f"{sorted(SUPPORTED_KEYS_IN_INJECTORS)}"
            ),
        ),
        (
            {"extra_vars": {"username": "{{ name }}"}},
            status.HTTP_400_BAD_REQUEST,
            "Injector key: username has a value which refers to an undefined "
            "key error",
        ),
    ],
)
def test_partial_update_injectors_credential_type(
    superuser_client: APIClient,
    new_injectors,
    status_code,
    message,
):
    obj = models.CredentialType.objects.create(
        name="type",
        inputs={"fields": [{"id": "username", "label": "Username"}]},
        injectors={"extra_vars": {"username": "Fred"}},
        managed=False,
    )
    data = {"injectors": new_injectors}
    response = superuser_client.patch(
        f"{api_url_v1}/credential-types/{obj.id}/", data=data
    )
    assert response.status_code == status_code

    if status_code == status.HTTP_200_OK:
        obj.refresh_from_db()
        assert obj.injectors == new_injectors
    else:
        assert message in str(response.data["injectors"])


@pytest.mark.django_db
def test_update_managed_credential_type(
    superuser_client: APIClient, preseed_credential_types
):
    scm = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.SOURCE_CONTROL,
    )
    data = {"name": "new_name"}
    response = superuser_client.patch(
        f"{api_url_v1}/credential-types/{scm.id}/", data=data
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "Managed credential type cannot be updated" in response.data["errors"]
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("data", "status_code", "key", "message"),
    [
        (
            {"name": "new_name"},
            status.HTTP_200_OK,
            "name",
            None,
        ),
        (
            {"injectors": {"user_name": "changed"}},
            status.HTTP_400_BAD_REQUEST,
            "injectors",
            (
                "Modifications to injectors are not allowed for "
                "credential types that are in use"
            ),
        ),
        (
            {"inputs": {"id": "user_password"}},
            status.HTTP_400_BAD_REQUEST,
            "inputs",
            (
                "Modifications to inputs are not allowed for "
                "credential types that are in use"
            ),
        ),
        (
            {
                "name": "new_name",
                "inputs": {"id": "user_password"},
                "injectors": {"user_password": "secret"},
            },
            status.HTTP_400_BAD_REQUEST,
            "inputs",
            (
                "Modifications to inputs are not allowed for "
                "credential types that are in use"
            ),
        ),
    ],
)
def test_update_credential_type_with_created_credentials(
    superuser_client: APIClient,
    default_organization: models.Organization,
    preseed_credential_types,
    data,
    status_code,
    key,
    message,
):
    user_type = models.CredentialType.objects.create(
        name="user_type",
        inputs={"fields": [{"id": "username"}]},
        injectors={},
        managed=False,
    )
    models.EdaCredential.objects.create(
        name="test-eda-credential",
        inputs={"username": "adam"},
        credential_type_id=user_type.id,
        organization=default_organization,
    )

    response = superuser_client.patch(
        f"{api_url_v1}/credential-types/{user_type.id}/", data=data
    )
    assert response.status_code == status_code
    if message is not None:
        assert message in response.data[key]


@pytest.mark.django_db
def test_credential_types_based_on_namespace(
    admin_client: APIClient,
    preseed_credential_types,
):
    response = admin_client.get(
        f"{api_url_v1}/credential-types/?namespace=event_stream"
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    for credential_type in data["results"]:
        assert credential_type["namespace"] == "event_stream"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("inputs", "injectors", "status_code", "key", "message"),
    [
        (
            {
                "fields": [
                    {"id": "cert", "label": "Certificate", "type": "string"},
                    {"id": "key", "label": "Key", "type": "string"},
                ]
            },
            {
                "file": {
                    "template.cert_file": "[mycert]\n{{ cert }}",
                    "template.key_file": "[mykey]\n{{ key }}",
                },
            },
            status.HTTP_201_CREATED,
            "",
            None,
        ),
        (
            {
                "fields": [
                    {"id": "cert", "label": "Certificate", "type": "string"},
                    {"id": "key", "label": "Key", "type": "string"},
                ]
            },
            {
                "file": {
                    "template.cert_file": "[mycert]\n{{ cert }}",
                    "xyz.cert_file": "[mykey]\n{{ key }}",
                },
            },
            status.HTTP_400_BAD_REQUEST,
            "injectors",
            ("Injector file key: xyz.cert_file should start with template"),
        ),
        (
            {
                "fields": [
                    {"id": "cert", "label": "Certificate", "type": "string"},
                    {"id": "key", "label": "Key", "type": "string"},
                ]
            },
            {
                "file": {
                    "template": "[mycert]\n{{ cert }}",
                },
            },
            status.HTTP_201_CREATED,
            "",
            None,
        ),
        (
            {
                "fields": [
                    {"id": "cert", "label": "Certificate", "type": "string"},
                    {"id": "key", "label": "Key", "type": "string"},
                ]
            },
            {
                "file": {
                    "template.cert_file": "[mycert]\n{{ cert }}",
                    "template.cert_file.abc": "[mykey]\n{{ key }}",
                },
            },
            status.HTTP_400_BAD_REQUEST,
            "injectors",
            (
                "Injector file key: template.cert_file.abc "
                "cannot contain multiple dots"
            ),
        ),
    ],
)
def test_create_credential_type_with_file(
    superuser_client: APIClient,
    inputs: dict,
    injectors: dict,
    status_code: int,
    key: str,
    message: Optional[str],
):
    data_in = {
        "name": "credential_type_1",
        "description": "desc here",
        "inputs": inputs,
        "injectors": injectors,
    }

    response = superuser_client.post(
        f"{api_url_v1}/credential-types/", data=data_in
    )
    assert response.status_code == status_code
    if message and key:
        assert message in response.data[key]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("inputs", "injectors", "status_code", "key", "message"),
    [
        (
            {
                "fields": [
                    {"id": "name", "label": "Name", "type": "string"},
                    {"id": "age", "label": "Age", "type": "string"},
                ]
            },
            {
                "extra_vars": {
                    "template.filename": "{{ name }}",
                    "age": "{{ age }}",
                },
                "file": {"template.filename": "Name = {{ name }}"},
            },
            status.HTTP_400_BAD_REQUEST,
            "injectors",
            "template.filename already exists",
        ),
        (
            {
                "fields": [
                    {"id": "name", "label": "Name", "type": "string"},
                    {"id": "age", "label": "Age", "type": "string"},
                ]
            },
            {
                "extra_vars": {
                    "name": "{{ name }}",
                    "age": "{{ age }}",
                },
                "file": {"template.filename": "Name = {{ name }}"},
            },
            status.HTTP_201_CREATED,
            "",
            "",
        ),
    ],
)
def test_create_credential_type_with_duplicates(
    superuser_client: APIClient,
    inputs: dict,
    injectors: dict,
    status_code: int,
    key: str,
    message: str,
):
    data_in = {
        "name": "credential_type_1",
        "inputs": inputs,
        "injectors": injectors,
    }

    response = superuser_client.post(
        f"{api_url_v1}/credential-types/", data=data_in
    )
    assert response.status_code == status_code
    if message and key:
        assert message in response.data[key][0]
