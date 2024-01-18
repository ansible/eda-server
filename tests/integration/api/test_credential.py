import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.api.constants import EDA_SERVER_VAULT_LABEL
from aap_eda.core import models
from aap_eda.core.enums import CredentialType
from tests.integration.api.test_activation import (
    create_activation,
    create_activation_related_data,
)
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
        "credential_type": CredentialType.REGISTRY,
        "id": obj.id,
        "key": None,
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
        "credential_type": CredentialType.REGISTRY,
        "id": id_,
        "key": None,
    }
    obj = models.Credential.objects.filter(pk=id_).first()
    assert obj.username == "me"
    assert obj.secret == "mypassword"


@pytest.mark.parametrize(
    "credential_type",
    [CredentialType.EXTRA_VAR, CredentialType.VAULT_PASSWORD],
)
@pytest.mark.django_db
def test_create_credential_with_missing_key_error(
    client: APIClient, credential_type
):
    data_in = {
        "name": "credential1",
        "description": "desc here",
        "username": "me",
        "secret": "mypassword",
        "credential_type": credential_type,
    }
    response = client.post(f"{api_url_v1}/credentials/", data=data_in)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        f"Key field is required when type is {credential_type}"
        in response.data["non_field_errors"]
    )


@pytest.mark.django_db
def test_create_credential_with_duplicate_key_error(client: APIClient):
    unique_key = "unique"
    models.Credential.objects.create(
        name="credential",
        description="desc here",
        username="me",
        key=unique_key,
        secret="mypassword",
        credential_type=CredentialType.EXTRA_VAR,
    )

    extra_data_in = {
        "name": "credential1",
        "description": "desc here",
        "username": "me",
        "key": unique_key,
        "secret": "mypassword",
        "credential_type": CredentialType.EXTRA_VAR,
    }
    response = client.post(f"{api_url_v1}/credentials/", data=extra_data_in)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        f"Duplicate {unique_key} found in credentials"
        in response.data["non_field_errors"]
    )

    vault_data_in = {
        "name": "credential1",
        "description": "desc here",
        "username": "me",
        "key": unique_key,
        "secret": "mypassword",
        "credential_type": CredentialType.VAULT_PASSWORD,
    }
    response = client.post(f"{api_url_v1}/credentials/", data=vault_data_in)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["credential_type"] == CredentialType.VAULT_PASSWORD


@pytest.mark.django_db
def test_create_credential_with_reserved_error(client: APIClient):
    vault_data_in = {
        "name": "credential",
        "description": "desc here",
        "username": "me",
        "key": EDA_SERVER_VAULT_LABEL,
        "secret": "mypassword",
        "credential_type": CredentialType.VAULT_PASSWORD,
    }
    response = client.post(f"{api_url_v1}/credentials/", data=vault_data_in)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        f"{EDA_SERVER_VAULT_LABEL} is reserved by EDA for vault labels"
        in response.data["non_field_errors"]
    )


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
        "credential_type": CredentialType.REGISTRY,
        "id": obj.id,
        "key": None,
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
        "credential_type": CredentialType.REGISTRY,
        "id": obj.id,
        "key": None,
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
def test_delete_credential_not_exist(client: APIClient):
    response = client.delete(f"{api_url_v1}/credentials/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_delete_credential_used_by_activation(client: APIClient):
    # TODO(alex) presetup should be a reusable fixture
    activation_dependencies = create_activation_related_data()
    create_activation(activation_dependencies)
    credential_id = activation_dependencies["credential_id"]
    response = client.delete(f"{api_url_v1}/credentials/{credential_id}/")
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_delete_credential_used_by_activation_forced(client: APIClient):
    # TODO(alex) presetup should be a reusable fixture
    activation_dependencies = create_activation_related_data()
    create_activation(activation_dependencies)
    credential_id = activation_dependencies["credential_id"]
    response = client.delete(
        f"{api_url_v1}/credentials/{credential_id}/?force=true",
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


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
