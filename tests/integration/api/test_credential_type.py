import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_create_credential_type(client: APIClient):
    data_in = {
        "name": "credential_type_1",
        "description": "desc here",
        "inputs": {"a": "b"},
        "injectors": {"a": "b"},
    }
    response = client.post(f"{api_url_v1}/credential-types/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "credential_type_1"


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
def test_partial_update_credential_type(client: APIClient):
    obj = models.CredentialType.objects.create(
        name="type1",
        inputs={"fields": [{"a": "b"}]},
        injectors={},
        managed=False,
    )
    data = {"inputs": {"fields": "changed"}}
    response = client.patch(
        f"{api_url_v1}/credential-types/{obj.id}/", data=data
    )
    assert response.status_code == status.HTTP_200_OK
    result = response.data
    assert result["inputs"] == {"fields": "changed"}
