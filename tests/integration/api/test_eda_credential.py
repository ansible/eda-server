import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import enums, models
from tests.integration.api.test_activation import (
    create_activation,
    create_activation_related_data,
)
from tests.integration.constants import api_url_v1

INPUTS = {
    "fields": [
        {"id": "username", "label": "Username", "type": "string"},
        {
            "id": "password",
            "label": "Password",
            "type": "string",
            "secret": True,
        },
        {
            "id": "ssh_key_data",
            "label": "SCM Private Key",
            "type": "string",
            "format": "ssh_private_key",
            "secret": True,
            "multiline": True,
        },
        {
            "id": "ssh_key_unlock",
            "label": "Private Key Passphrase",
            "type": "string",
            "secret": True,
        },
    ]
}


@pytest.mark.django_db
def test_create_eda_credential(
    client: APIClient,
    credential_type: models.CredentialType,
):
    data_in = {
        "name": "eda-credential",
        "inputs": {"username": "adam", "password": "secret"},
        "credential_type_id": credential_type.id,
    }
    response = client.post(f"{api_url_v1}/eda-credentials/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "eda-credential"
    assert response.data["managed"] is False


@pytest.mark.django_db
def test_create_eda_credential_with_type(
    client: APIClient, credential_type: models.CredentialType
):
    data_in = {
        "name": "eda-credential",
        "inputs": {"username": "adam", "password": "secret"},
        "credential_type_id": credential_type.id,
    }
    response = client.post(f"{api_url_v1}/eda-credentials/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "eda-credential"
    assert response.data["managed"] is False
    assert response.data["inputs"] == {
        "password": "$encrypted$",
        "username": "adam",
    }


@pytest.mark.django_db
def test_retrieve_eda_credential(
    client: APIClient, credential_type: models.CredentialType
):
    obj = models.EdaCredential.objects.create(
        name="eda_credential",
        inputs={"username": "adam", "password": "secret"},
        managed=False,
        credential_type_id=credential_type.id,
    )
    response = client.get(f"{api_url_v1}/eda-credentials/{obj.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "eda_credential"
    assert response.data["inputs"] == {
        "username": "adam",
        "password": "$encrypted$",
    }
    assert response.data["managed"] is False


@pytest.mark.django_db
def test_list_eda_credentials(
    client: APIClient, credential_type: models.CredentialType
):
    models.EdaCredential.objects.bulk_create(
        [
            models.EdaCredential(
                name="credential-1",
                inputs={"username": "adam", "password": "secret"},
                credential_type_id=credential_type.id,
            ),
            models.EdaCredential(
                name="credential-2",
                inputs={"username": "bearny", "password": "secret"},
                credential_type_id=credential_type.id,
            ),
            models.EdaCredential(
                name="credential-3",
                inputs={"username": "christ", "password": "secret"},
                credential_type_id=credential_type.id,
                managed=True,
            ),
        ]
    )
    response = client.get(f"{api_url_v1}/eda-credentials/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 2
    assert response.data["results"][0]["name"] == "credential-1"
    assert response.data["results"][0]["inputs"] == {
        "username": "adam",
        "password": "$encrypted$",
    }
    assert response.data["results"][1]["name"] == "credential-2"
    assert response.data["results"][1]["inputs"] == {
        "username": "bearny",
        "password": "$encrypted$",
    }


@pytest.mark.django_db
def test_list_eda_credentials_with_kind_filter(
    client: APIClient, credential_type: models.CredentialType
):
    registry_type = models.CredentialType.objects.create(
        name="registry", inputs=INPUTS, injectors={}, kind="registry"
    )
    scm_type = models.CredentialType.objects.create(
        name="scm", inputs=INPUTS, injectors={}, kind="scm"
    )
    models.EdaCredential.objects.bulk_create(
        [
            models.EdaCredential(
                name="credential-1",
                inputs={"username": "adam", "password": "secret"},
                credential_type_id=registry_type.id,
            ),
            models.EdaCredential(
                name="credential-2",
                inputs={"username": "bearny", "password": "secret"},
                credential_type_id=scm_type.id,
            ),
            models.EdaCredential(
                name="credential-3",
                inputs={"username": "christ", "password": "secret"},
                credential_type_id=scm_type.id,
            ),
        ]
    )

    response = client.get(
        f"{api_url_v1}/eda-credentials/?credential_type__kind=scm"
    )
    assert len(response.data["results"]) == 2

    response = client.get(
        f"{api_url_v1}/eda-credentials/?credential_type__kind=registry"
    )
    assert len(response.data["results"]) == 1

    response = client.get(
        f"{api_url_v1}/eda-credentials/?credential_type__kind=vault"
    )
    assert len(response.data["results"]) == 0

    response = client.get(
        f"{api_url_v1}/eda-credentials/?credential_type__kind=scm"
        "&credential_type__kind=vault",
    )
    assert len(response.data["results"]) == 2

    response = client.get(
        f"{api_url_v1}/eda-credentials/?credential_type__kind=scm"
        "&credential_type__kind=registry",
    )
    assert len(response.data["results"]) == 3


@pytest.mark.django_db
def test_list_eda_credentials_filter_credential_type_id(
    client: APIClient, preseed_credential_types
):
    registry_type = models.CredentialType.objects.create(
        name="registry", inputs=INPUTS, injectors={}, kind="registry"
    )
    scm_type = models.CredentialType.objects.create(
        name="scm", inputs=INPUTS, injectors={}, kind="scm"
    )
    models.EdaCredential.objects.bulk_create(
        [
            models.EdaCredential(
                name="credential-1",
                inputs={"username": "adam", "password": "secret"},
                credential_type_id=registry_type.id,
            ),
            models.EdaCredential(
                name="credential-2",
                inputs={"username": "bearny", "password": "secret"},
                credential_type_id=scm_type.id,
            ),
            models.EdaCredential(
                name="credential-3",
                inputs={"username": "christ", "password": "secret"},
                credential_type_id=scm_type.id,
            ),
        ]
    )

    response = client.get(
        f"{api_url_v1}/eda-credentials/?credential_type_id={registry_type.id}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1

    response = client.get(
        f"{api_url_v1}/eda-credentials/?credential_type_id={scm_type.id}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 2


@pytest.mark.django_db
def test_list_eda_credentials_filter_name(
    client: APIClient, preseed_credential_types
):
    credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )

    models.EdaCredential.objects.bulk_create(
        [
            models.EdaCredential(
                name="credential-1",
                inputs={"username": "adam", "password": "secret"},
                credential_type_id=credential_type.id,
            ),
            models.EdaCredential(
                name="new-credential",
                inputs={"username": "bearny", "password": "secret"},
                credential_type_id=credential_type.id,
            ),
            models.EdaCredential(
                name="new-test-credential",
                inputs={"username": "christ", "password": "secret"},
                credential_type_id=credential_type.id,
            ),
        ]
    )

    response = client.get(f"{api_url_v1}/eda-credentials/?name=credential")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1

    response = client.get(f"{api_url_v1}/eda-credentials/?name=new")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 2


@pytest.mark.django_db
def test_delete_eda_credential(client: APIClient):
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs={"username": "adam", "password": "secret"},
    )
    response = client.delete(f"{api_url_v1}/eda-credentials/{obj.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert models.EdaCredential.objects.count() == 0


@pytest.mark.django_db
def test_delete_managed_eda_credential(client: APIClient):
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs={"username": "adam", "password": "secret"},
        managed=True,
    )
    response = client.delete(f"{api_url_v1}/eda-credentials/{obj.id}/")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["errors"] == "Managed EDA credential cannot be deleted"
    )


@pytest.mark.django_db
def test_partial_update_eda_credential(
    client: APIClient, credential_type: models.CredentialType
):
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs={"username": "adam", "password": "secret", "key": "private"},
        credential_type_id=credential_type.id,
        managed=True,
    )
    data = {"inputs": {"username": "bearny", "password": "demo"}}
    response = client.patch(
        f"{api_url_v1}/eda-credentials/{obj.id}/", data=data
    )
    assert response.status_code == status.HTTP_200_OK
    result = response.data
    assert result["inputs"] == {
        "password": "$encrypted$",
        "username": "bearny",
        "key": "private",
    }


@pytest.mark.django_db
def test_partial_update_eda_credential_name(
    client: APIClient, credential_type: models.CredentialType
):
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs={"username": "adam", "password": "secret", "key": "private"},
        credential_type_id=credential_type.id,
        managed=True,
    )
    data = {"name": "demo2"}
    response = client.patch(
        f"{api_url_v1}/eda-credentials/{obj.id}/", data=data
    )
    assert response.status_code == status.HTTP_200_OK
    result = response.data
    assert result["inputs"] == {
        "password": "$encrypted$",
        "username": "adam",
        "key": "private",
    }
    assert result["name"] == "demo2"


@pytest.mark.django_db
def test_delete_credential_with_de_reference(
    client: APIClient, preseed_credential_types
):
    credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    eda_credential = models.EdaCredential.objects.create(
        name="test-credential",
        description="test credential",
        credential_type=credential_type,
        inputs={"username": "dummy-user", "password": "dummy-password"},
    )

    models.DecisionEnvironment.objects.create(
        name="test_de_name",
        image_url="quay.io/de/image_url",
        description="test_de_description",
        eda_credential_id=eda_credential.id,
    )
    response = client.delete(
        f"{api_url_v1}/eda-credentials/{eda_credential.id}/"
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        f"Credential {eda_credential.name} is being referenced by other "
        "resources and cannot be deleted"
    ) in response.data["detail"]


@pytest.mark.django_db
def test_delete_credential_with_project_reference(
    client: APIClient, preseed_credential_types
):
    credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    eda_credential = models.EdaCredential.objects.create(
        name="test-credential",
        description="test credential",
        credential_type=credential_type,
        inputs={"username": "dummy-user", "password": "dummy-password"},
    )

    models.Project.objects.create(
        git_hash="git_hash",
        name="test_project_name",
        url="https://git_image_url",
        description="test_project_description",
        eda_credential_id=eda_credential.id,
    )
    response = client.delete(
        f"{api_url_v1}/eda-credentials/{eda_credential.id}/"
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        f"Credential {eda_credential.name} is being referenced by other "
        "resources and cannot be deleted"
    ) in response.data["detail"]


@pytest.mark.django_db
def test_delete_credential_with_activation_reference(
    client: APIClient, preseed_credential_types
):
    credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    eda_credential = models.EdaCredential.objects.create(
        name="test-credential",
        description="test credential",
        credential_type=credential_type,
        inputs={"username": "dummy-user", "password": "dummy-password"},
    )

    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    activation = models.Activation.objects.create(
        name="test_activation",
        user=user,
    )
    activation.eda_credentials.add(eda_credential)

    response = client.delete(
        f"{api_url_v1}/eda-credentials/{eda_credential.id}/"
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        f"Credential {eda_credential.name} is being referenced by other "
        "resources and cannot be deleted"
    ) in response.data["detail"]


@pytest.mark.django_db
def test_delete_credential_used_by_forced(
    client: APIClient, preseed_credential_types
):
    activation_dependencies = create_activation_related_data()
    create_activation(activation_dependencies)

    assert models.EdaCredential.objects.count() == 1
    eda_credential_id = activation_dependencies["eda_credential_id"]
    response = client.delete(
        f"{api_url_v1}/eda-credentials/{eda_credential_id}/?force=true",
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert models.EdaCredential.objects.count() == 0


@pytest.mark.parametrize("refs", ["true", "false"])
@pytest.mark.django_db
def test_retrieve_eda_credential_with_refs(
    client: APIClient, refs, preseed_credential_types
):
    activation_dependencies = create_activation_related_data()
    activation = create_activation(activation_dependencies)
    eda_credential_id = activation_dependencies["eda_credential_id"]
    decision_environment = models.DecisionEnvironment.objects.get(
        eda_credential_id=eda_credential_id
    )
    eda_credential = models.EdaCredential.objects.get(id=eda_credential_id)
    activation.eda_credentials.add(eda_credential)

    response = client.get(
        f"{api_url_v1}/eda-credentials/{eda_credential_id}/?refs={refs}",
    )
    assert response.status_code == status.HTTP_200_OK

    if refs == "true":
        assert response.data["references"] is not None
        references = response.data["references"]

        assert len(references) == 2
        references[0] = {
            "type": "Activation",
            "id": activation.id,
            "name": activation.name,
            "url": f"api/eda/v1/activations/{activation.id}/",
        }
        references[1] = {
            "type": "DecisionEnvironment",
            "id": decision_environment.id,
            "name": decision_environment.name,
            "url": (
                f"api/eda/v1/decision_environments/{decision_environment.id}/"
            ),
        }
    else:
        assert response.data["references"] is None


@pytest.mark.django_db
def test_retrieve_eda_credential_with_empty_encrypted_fields(
    client: APIClient, preseed_credential_types
):
    scm_type = models.CredentialType.objects.filter(name="Source Control")[0]
    data_in = {
        "name": "scm-credential",
        "inputs": {
            "username": "adam",
            "password": "secret",
            "ssh_key_unlock": "",
        },
        "credential_type_id": scm_type.id,
    }
    response = client.post(f"{api_url_v1}/eda-credentials/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    key_list = list(response.data["inputs"].keys())
    assert "ssh_key_unlock" not in key_list
    assert key_list[0] == "username"
    assert key_list[1] == "password"
