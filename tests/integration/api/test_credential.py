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
        "vault_identifier": None,
        "scm_ssh_key": None,
        "scm_ssh_key_passphrase": None,
    }


@pytest.mark.parametrize(
    # The "response" params are combined with the "create" params for
    # checking.
    "params",
    [
        {
            "create": {
                "name": "credential1",
                "description": "desc here",
                "username": "me",
                "secret": "mypassword",
            },
            "response": {
                "credential_type": CredentialType.REGISTRY,
                "scm_ssh_key": None,
                "scm_ssh_key_passphrase": None,
                "vault_identifier": None,
            },
        },
        {
            "create": {
                "name": "credential1",
                "description": "desc here",
                "secret": "mypassword",
                "credential_type": CredentialType.SCM,
            },
            "response": {
                "username": None,
                "scm_ssh_key": None,
                "scm_ssh_key_passphrase": None,
                "vault_identifier": None,
            },
        },
        {
            "create": {
                "name": "credential1",
                "description": "desc here",
                "username": "me",
                "secret": "mypassword",
                "credential_type": CredentialType.SCM,
            },
            "response": {
                "scm_ssh_key": None,
                "scm_ssh_key_passphrase": None,
                "vault_identifier": None,
            },
        },
        {
            "create": {
                "name": "credential1",
                "description": "desc here",
                "scm_ssh_key": "bogus-key",
                "scm_ssh_key_passphrase": "bogus-key-password",
                "credential_type": CredentialType.SCM,
            },
            "response": {
                "username": None,
                "secret": None,
                "vault_identifier": None,
            },
        },
        {
            "create": {
                "name": "credential1",
                "description": "desc here",
                "secret": "mypassword",
                "scm_ssh_key": "bogus-key",
                "scm_ssh_key_passphrase": "bogus-key-password",
                "credential_type": CredentialType.SCM,
            },
            "response": {
                "username": None,
                "vault_identifier": None,
            },
        },
        {
            "create": {
                "name": "credential1",
                "description": "desc here",
                "username": "me",
                "secret": "mypassword",
                "scm_ssh_key": "bogus-key",
                "scm_ssh_key_passphrase": "bogus-key-password",
                "credential_type": CredentialType.SCM,
            },
            "response": {
                "vault_identifier": None,
            },
        },
        {
            "status": status.HTTP_400_BAD_REQUEST,
            "create": {
                "name": "credential1",
                "description": "desc here",
                "credential_type": CredentialType.SCM,
            },
            "response": {},
        },
        {
            "status": status.HTTP_400_BAD_REQUEST,
            "create": {
                "name": "credential1",
                "description": "desc here",
                "scm_ssh_key": "bogus-key",
                "credential_type": CredentialType.SCM,
            },
            "response": {},
        },
        {
            "status": status.HTTP_400_BAD_REQUEST,
            "create": {
                "name": "credential1",
                "description": "desc here",
                "scm_ssh_key_passphrase": "bogus-key-password",
                "credential_type": CredentialType.SCM,
            },
            "response": {},
        },
    ],
)
@pytest.mark.django_db
def test_create_credential(client: APIClient, params):
    expected_status = params.get("status", status.HTTP_201_CREATED)
    create_data = params["create"]
    response_data = create_data | params["response"]
    username = response_data.get("username", None)
    secret = response_data.pop("secret", None)

    response = client.post(f"{api_url_v1}/credentials/", data=create_data)
    assert response.status_code == expected_status
    if response.status_code == status.HTTP_201_CREATED:
        id_ = response.data["id"]
        result = response.data
        result.pop("created_at")
        result.pop("modified_at")
        assert result == (response_data | {"id": id_})

        obj = models.Credential.objects.filter(pk=id_).first()
        assert obj.username == username
        assert obj.secret == secret
        if response_data["credential_type"] == CredentialType.SCM:
            assert (
                (response_data["scm_ssh_key"] is None)
                and (response_data["scm_ssh_key_passphrase"] is None)
            ) or (
                (response_data["scm_ssh_key"] is not None)
                and (response_data["scm_ssh_key_passphrase"] is not None)
            )
            if secret is None:
                assert response_data["scm_ssh_key"] is not None
            if response_data["scm_ssh_key"] is None:
                assert secret is not None


@pytest.mark.django_db
def test_create_credential_without_identifier(client: APIClient):
    vault_data_in = {
        "name": "credential",
        "description": "desc here",
        "username": "me",
        "secret": "mypassword",
        "credential_type": CredentialType.VAULT,
    }
    response = client.post(f"{api_url_v1}/credentials/", data=vault_data_in)
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_create_credential_with_reserved_error(client: APIClient):
    vault_data_in = {
        "name": "credential",
        "description": "desc here",
        "username": "me",
        "vault_identifier": EDA_SERVER_VAULT_LABEL,
        "secret": "mypassword",
        "credential_type": CredentialType.VAULT,
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
        "vault_identifier": None,
        "scm_ssh_key": None,
        "scm_ssh_key_passphrase": None,
    }


@pytest.mark.django_db
def test_retrieve_vault_credential(client: APIClient):
    obj = models.Credential.objects.create(
        name="credential1",
        username="me",
        secret="sec1",
        credential_type=CredentialType.VAULT,
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
        "credential_type": CredentialType.VAULT,
        "id": obj.id,
        "vault_identifier": None,
        "scm_ssh_key": None,
        "scm_ssh_key_passphrase": None,
    }


@pytest.mark.django_db
def test_retrieve_sytem_vault_credential(client: APIClient):
    obj = models.Credential.objects.create(
        name="credential1",
        username="me",
        secret="sec1",
        credential_type=CredentialType.VAULT,
        vault_identifier=EDA_SERVER_VAULT_LABEL,
    )
    response = client.get(f"{api_url_v1}/credentials/{obj.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_retrieve_credential_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/credentials/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_list_exclude_reserved_vault_credentials(client: APIClient):
    credentials = models.Credential.objects.bulk_create(
        [
            models.Credential(
                name="credential1",
                username="me",
                secret="sec1",
            ),
            models.Credential(
                name="credential2",
                username="me",
                secret="sec2",
                credential_type=CredentialType.VAULT,
            ),
            models.Credential(
                name="credential3",
                username="me",
                secret="sec3",
                vault_identifier=EDA_SERVER_VAULT_LABEL,
                credential_type=CredentialType.VAULT,
            ),
        ]
    )
    response = client.get(f"{api_url_v1}/credentials/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 2
    assert response.data["results"][0]["name"] == credentials[0].name
    assert response.data["results"][1]["name"] == credentials[1].name


@pytest.mark.parametrize(
    # The "response" params are combined with the "create" and "update" params
    # for checking.
    "params",
    [
        {
            "create": {
                "name": "credential1",
                "description": "desc here",
                "username": "me",
                "secret": "sec1",
            },
            "update": {
                "secret": "sec2",
            },
            "response": {
                "credential_type": CredentialType.REGISTRY,
                "scm_ssh_key": None,
                "scm_ssh_key_passphrase": None,
                "vault_identifier": None,
            },
        },
        {
            "create": {
                "name": "credential1",
                "description": "desc here",
                "secret": "mypassword",
                "credential_type": CredentialType.SCM,
            },
            "update": {
                "secret": "sec2",
            },
            "response": {
                "username": None,
                "scm_ssh_key": None,
                "scm_ssh_key_passphrase": None,
                "vault_identifier": None,
            },
        },
        {
            "create": {
                "name": "credential1",
                "description": "desc here",
                "username": "me",
                "secret": "mypassword",
                "credential_type": CredentialType.SCM,
            },
            "update": {
                "secret": "another-secret",
            },
            "response": {
                "scm_ssh_key": None,
                "scm_ssh_key_passphrase": None,
                "vault_identifier": None,
            },
        },
        {
            "create": {
                "name": "credential1",
                "description": "desc here",
                "scm_ssh_key": "bogus-key",
                "scm_ssh_key_passphrase": "bogus-key-password",
                "credential_type": CredentialType.SCM,
            },
            "update": {
                "scm_ssh_key": "another-bogus-key",
                "scm_ssh_key_passphrase": "another-bogus-key-password",
            },
            "response": {
                "username": None,
                "secret": None,
                "vault_identifier": None,
            },
        },
        {
            "create": {
                "name": "credential1",
                "description": "desc here",
                "secret": "mypassword",
                "scm_ssh_key": "bogus-key",
                "scm_ssh_key_passphrase": "bogus-key-password",
                "credential_type": CredentialType.SCM,
            },
            "update": {
                "secret": "another-secret",
                "scm_ssh_key": "another-bogus-key",
                "scm_ssh_key_passphrase": "another-bogus-key-password",
            },
            "response": {
                "username": None,
                "vault_identifier": None,
            },
        },
        {
            "create": {
                "name": "credential1",
                "description": "desc here",
                "username": "me",
                "secret": "mypassword",
                "scm_ssh_key": "bogus-key",
                "scm_ssh_key_passphrase": "bogus-key-password",
                "credential_type": CredentialType.SCM,
            },
            "update": {
                "secret": "another-secret",
            },
            "response": {
                "vault_identifier": None,
            },
        },
        {
            "create": {
                "name": "credential1",
                "description": "desc here",
                "username": "me",
                "secret": "mypassword",
                "scm_ssh_key": "bogus-key",
                "scm_ssh_key_passphrase": "bogus-key-password",
                "credential_type": CredentialType.SCM,
            },
            "update": {
                "secret": None,
            },
            "response": {
                "vault_identifier": None,
            },
        },
        {
            "create": {
                "name": "credential1",
                "description": "desc here",
                "username": "me",
                "secret": "mypassword",
                "scm_ssh_key": "bogus-key",
                "scm_ssh_key_passphrase": "bogus-key-password",
                "credential_type": CredentialType.SCM,
            },
            "update": {
                "scm_ssh_key": "another-bogus-key",
                "scm_ssh_key_passphrase": "another-bogus-key-password",
            },
            "response": {
                "vault_identifier": None,
            },
        },
        {
            "create": {
                "name": "credential1",
                "description": "desc here",
                "username": "me",
                "secret": "mypassword",
                "scm_ssh_key": "bogus-key",
                "scm_ssh_key_passphrase": "bogus-key-password",
                "credential_type": CredentialType.SCM,
            },
            "update": {
                "scm_ssh_key": None,
                "scm_ssh_key_passphrase": None,
            },
            "response": {
                "vault_identifier": None,
            },
        },
        {
            "status": status.HTTP_400_BAD_REQUEST,
            "create": {
                "name": "credential1",
                "description": "desc here",
                "username": "me",
                "secret": "mypassword",
                "scm_ssh_key": "bogus-key",
                "scm_ssh_key_passphrase": "bogus-key-password",
                "credential_type": CredentialType.SCM,
            },
            "update": {
                "scm_ssh_key": "another-bogus-key",
            },
            "response": {},
        },
        {
            "status": status.HTTP_400_BAD_REQUEST,
            "create": {
                "name": "credential1",
                "description": "desc here",
                "username": "me",
                "secret": "mypassword",
                "scm_ssh_key": "bogus-key",
                "scm_ssh_key_passphrase": "bogus-key-password",
                "credential_type": CredentialType.SCM,
            },
            "update": {
                "scm_ssh_key_passphrase": "another-bogus-key-password",
            },
            "response": {},
        },
    ],
)
@pytest.mark.django_db
def test_partial_update_credential(client: APIClient, params):
    expected_status = params.get("status", status.HTTP_200_OK)
    create_data = params["create"]
    update_data = params["update"]
    response_data = create_data | params["update"] | params["response"]
    secret = response_data.pop("secret", None)
    ssh_key = response_data.pop("scm_ssh_key", None)
    ssh_key_passphrase = response_data.pop("scm_ssh_key_passphrase", None)

    obj = models.Credential.objects.create(**create_data)

    response = client.patch(
        f"{api_url_v1}/credentials/{obj.id}/", data=update_data
    )
    assert response.status_code == expected_status
    if response.status_code == status.HTTP_200_OK:
        result = response.data
        result.pop("created_at")
        result.pop("modified_at")
        result.pop("scm_ssh_key")
        result.pop("scm_ssh_key_passphrase")
        assert result == (response_data | {"id": obj.id})

        updated_obj = models.Credential.objects.filter(pk=obj.id).first()
        assert updated_obj.secret == secret
        assert updated_obj.scm_ssh_key == ssh_key
        assert updated_obj.scm_ssh_key_passphrase == ssh_key_passphrase


@pytest.mark.django_db
def test_update_vault_credential(client: APIClient):
    obj = models.Credential.objects.create(
        name="credential1",
        username="me",
        secret="sec1",
        credential_type=CredentialType.VAULT,
    )
    data = {"vault_identifier": "EDA_SERVER_TEST"}
    response = client.patch(f"{api_url_v1}/credentials/{obj.id}/", data=data)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["vault_identifier"] == "EDA_SERVER_TEST"


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
def test_delete_reserved_vault_credential(client: APIClient):
    obj = models.Credential.objects.create(
        name="credential1",
        username="me",
        secret="sec1",
        credential_type=CredentialType.VAULT,
        vault_identifier=EDA_SERVER_VAULT_LABEL,
    )
    response = client.delete(f"{api_url_v1}/credentials/{obj.id}/")
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == f"Credential {obj.id} is internal used."


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
