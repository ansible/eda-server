from typing import Any, Dict

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.api.constants import EDA_SERVER_VAULT_LABEL
from aap_eda.core import models
from aap_eda.core.enums import CredentialType
from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_list_credentials(
    default_credential: models.Credential, client: APIClient
):
    response = client.get(f"{api_url_v1}/credentials/")
    assert response.status_code == status.HTTP_200_OK
    result = response.data["results"][0]
    assert_credential_data(result, default_credential)


@pytest.mark.django_db
def test_create_credential(
    credential_payload: Dict[str, Any], client: APIClient
):
    response = client.post(
        f"{api_url_v1}/credentials/", data=credential_payload
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.data
    assert data["name"] == credential_payload["name"]
    assert data["description"] == credential_payload["description"]
    assert data["credential_type"] == credential_payload["credential_type"]
    assert data["username"] == credential_payload["username"]
    assert data["organization_id"] == credential_payload["organization_id"]
    # secret field isn't returned in response, assert it from db instead
    obj = models.Credential.objects.filter(pk=data["id"]).first()
    assert obj.username == credential_payload["username"]
    assert obj.secret == credential_payload["secret"]


@pytest.mark.django_db
def test_create_credential_without_identifier(
    credential_payload: Dict[str, Any], client: APIClient
):
    credential_payload["credential_type"] = CredentialType.VAULT
    response = client.post(
        f"{api_url_v1}/credentials/", data=credential_payload
    )
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_create_credential_with_reserved_error(
    credential_payload: Dict[str, Any], client: APIClient
):
    credential_payload["credential_type"] = CredentialType.VAULT
    credential_payload["vault_identifier"] = EDA_SERVER_VAULT_LABEL

    response = client.post(
        f"{api_url_v1}/credentials/", data=credential_payload
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        f"{EDA_SERVER_VAULT_LABEL} is reserved by EDA for vault labels"
        in response.data["non_field_errors"]
    )


@pytest.mark.django_db
def test_retrieve_credential(
    default_credential: models.Credential, client: APIClient
):
    response = client.get(f"{api_url_v1}/credentials/{default_credential.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert_credential_data(response.data, default_credential)


@pytest.mark.django_db
def test_retrieve_vault_credential(
    default_vault_credential: models.Credential, client: APIClient
):
    response = client.get(
        f"{api_url_v1}/credentials/{default_vault_credential.id}/"
    )
    assert response.status_code == status.HTTP_200_OK
    assert_credential_data(response.data, default_vault_credential)


@pytest.mark.django_db
def test_retrieve_system_vault_credential(
    default_eda_vault_credential: models.Credential, client: APIClient
):
    response = client.get(
        f"{api_url_v1}/credentials/{default_eda_vault_credential.id}/"
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_retrieve_credential_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/credentials/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_list_exclude_reserved_vault_credentials(
    default_credential: models.Credential,
    default_vault_credential: models.Credential,
    default_eda_vault_credential: models.Credential,
    client: APIClient,
):
    credentials = [
        default_credential,
        default_vault_credential,
        default_eda_vault_credential,
    ]
    response = client.get(f"{api_url_v1}/credentials/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 2
    assert response.data["results"][0]["name"] == credentials[0].name
    assert response.data["results"][1]["name"] == credentials[1].name


@pytest.mark.django_db
def test_partial_update_credential(
    default_credential: models.Credential, client: APIClient
):
    data = {"secret": "sec2"}
    response = client.patch(
        f"{api_url_v1}/credentials/{default_credential.id}/", data=data
    )
    assert response.status_code == status.HTTP_200_OK
    assert_credential_data(response.data, default_credential)
    # secret field isn't returned in response, assert it from db instead
    default_credential.refresh_from_db(fields=["secret"])
    assert default_credential.secret == data["secret"]


@pytest.mark.django_db
def test_update_vault_credential(
    default_vault_credential: models.Credential, client: APIClient
):
    data = {"vault_identifier": "EDA_SERVER_TEST"}
    response = client.patch(
        f"{api_url_v1}/credentials/{default_vault_credential.id}/", data=data
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["vault_identifier"] == data["vault_identifier"]


@pytest.mark.django_db
def test_delete_credential(
    default_credential: models.Credential, client: APIClient
):
    response = client.delete(
        f"{api_url_v1}/credentials/{default_credential.id}/"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert (
        models.Credential.objects.filter(pk=default_credential.id).count() == 0
    )


@pytest.mark.django_db
def test_delete_credential_not_exist(client: APIClient):
    response = client.delete(f"{api_url_v1}/credentials/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_delete_credential_used_by_activation(
    default_activation: models.Activation, client: APIClient
):
    credential_id = default_activation.decision_environment.credential_id
    response = client.delete(f"{api_url_v1}/credentials/{credential_id}/")
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_delete_credential_used_by_activation_forced(
    default_activation: models.Activation, client: APIClient
):
    credential_id = default_activation.decision_environment.credential_id
    response = client.delete(
        f"{api_url_v1}/credentials/{credential_id}/?force=true",
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_delete_reserved_vault_credential(
    default_eda_vault_credential: models.Credential, client: APIClient
):
    response = client.delete(
        f"{api_url_v1}/credentials/{default_eda_vault_credential.id}/"
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        response.data["detail"]
        == f"Credential {default_eda_vault_credential.id} is internal used."
    )


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


def assert_credential_data(
    response: Dict[str, Any], expected: models.Credential
) -> None:
    """Compare the response from a Credential view with db model object"""
    assert response["id"] == expected.id
    assert response["name"] == expected.name
    assert response["description"] == expected.description
    assert response["username"] == expected.username
    assert response["credential_type"] == expected.credential_type
    assert response["vault_identifier"] == expected.vault_identifier
    assert response["organization_id"] == expected.organization.id
