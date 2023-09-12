import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from aap_eda.core.enums import CredentialType
from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_list_credentials(client: APIClient):
    obj = models.Credential.objects.create(
        name="credential1", username="me", secret="sec1"
    )
    response = client.get(f"{api_url_v1}/credentials/")
    assert response.status_code == status.HTTP_200_OK
    result = response.data["results"][0]
    result.pop("created_at")
    result.pop("modified_at")
    assert result == {
        "name": "credential1",
        "description": "",
        "username": "me",
        "credential_type": CredentialType.REGISTRY.value,
        "id": obj.id,
    }


@pytest.mark.django_db
def test_create_credential(client: APIClient):
    data_in = {
        "name": "credential1",
        "description": "desc here",
        "username": "me",
        "secret": "mypassword",
    }
    response = client.post(f"{api_url_v1}/credentials/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    id_ = response.data["id"]
    result = response.data
    result.pop("created_at")
    result.pop("modified_at")
    assert result == {
        "name": "credential1",
        "description": "desc here",
        "username": "me",
        "credential_type": CredentialType.REGISTRY.value,
        "id": id_,
    }
    obj = models.Credential.objects.filter(pk=id_).first()
    assert obj.username == "me"
    assert obj.secret == "mypassword"


@pytest.mark.django_db
def test_retrieve_credential(client: APIClient):
    obj = models.Credential.objects.create(
        name="credential1", username="me", secret="sec1"
    )
    response = client.get(f"{api_url_v1}/credentials/{obj.id}/")
    assert response.status_code == status.HTTP_200_OK
    result = response.data
    result.pop("created_at")
    result.pop("modified_at")
    assert result == {
        "name": "credential1",
        "description": "",
        "username": "me",
        "credential_type": CredentialType.REGISTRY.value,
        "id": obj.id,
    }


@pytest.mark.django_db
def test_retrieve_credential_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/credentials/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_partial_update_credential(client: APIClient):
    obj = models.Credential.objects.create(
        name="credential1", username="me", secret="sec1"
    )
    data = {"secret": "sec2"}
    response = client.patch(f"{api_url_v1}/credentials/{obj.id}/", data=data)
    assert response.status_code == status.HTTP_200_OK
    result = response.data
    result.pop("created_at")
    result.pop("modified_at")
    assert result == {
        "name": "credential1",
        "description": "",
        "username": "me",
        "credential_type": CredentialType.REGISTRY.value,
        "id": obj.id,
    }
    updated_obj = models.Credential.objects.filter(pk=obj.id).first()
    assert updated_obj.secret == "sec2"


@pytest.mark.django_db
def test_delete_credential(client: APIClient):
    obj = models.Credential.objects.create(
        name="credential1", username="me", secret="sec1"
    )
    response = client.delete(f"{api_url_v1}/credentials/{obj.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert models.Credential.objects.filter(pk=obj.id).count() == 0


@pytest.mark.django_db
def test_credential_decrypt_failure(client: APIClient, settings):
    settings.SECRET_KEY = "a-secret-key"
    models.Credential.objects.create(
        name="credential1", username="me", secret="sec1"
    )

    response = client.get(f"{api_url_v1}/credentials/")
    assert response.status_code == status.HTTP_200_OK

    settings.SECRET_KEY = "a-different-secret-key"
    response = client.get(f"{api_url_v1}/credentials/")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    data = response.json()
    assert data["details"].startswith("Credential decryption failed")
