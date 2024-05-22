from pathlib import Path

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import enums, models
from tests.integration.conftest import DUMMY_GPG_KEY
from tests.integration.constants import api_url_v1

DATA_DIR = Path(__file__).parent.parent.parent / "unit/data"

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


@pytest.mark.parametrize(
    ("inputs", "status_code", "status_message"),
    [
        (
            {"username": "adam", "password": "secret"},
            status.HTTP_201_CREATED,
            None,
        ),
        (
            {"username": "adam", "password": "secret", "invalid_key": "bad"},
            status.HTTP_400_BAD_REQUEST,
            None,
        ),
    ],
)
@pytest.mark.django_db
def test_create_eda_credential(
    admin_client: APIClient,
    credential_type: models.CredentialType,
    inputs,
    status_code,
    status_message,
):
    data_in = {
        "name": "eda-credential",
        "inputs": inputs,
        "credential_type_id": credential_type.id,
    }
    response = admin_client.post(
        f"{api_url_v1}/eda-credentials/", data=data_in
    )
    assert response.status_code == status_code
    if status_code == status.HTTP_201_CREATED:
        assert response.data["name"] == "eda-credential"
        assert response.data["managed"] is False
    else:
        assert (
            "Input keys {'invalid_key'} are not defined in the schema"
            in response.data["inputs"][0]
        )


@pytest.mark.parametrize(
    ("key_file", "status_code", "status_message"),
    [
        (DATA_DIR / "public_key.asc", status.HTTP_201_CREATED, ""),
        (
            DATA_DIR / "private_key.asc",
            status.HTTP_400_BAD_REQUEST,
            "Key is not a public key",
        ),
        (
            DATA_DIR / "invalid_key.asc",
            status.HTTP_400_BAD_REQUEST,
            "No valid GPG data found.",
        ),
    ],
)
@pytest.mark.django_db
def test_create_eda_credential_with_gpg_key_data(
    admin_client: APIClient,
    preseed_credential_types,
    key_file,
    status_code,
    status_message,
):
    gpg_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.GPG
    )
    with open(key_file) as f:
        key_data = f.read()

    data_in = {
        "name": "eda-credential",
        "inputs": {"gpg_public_key": key_data},
        "credential_type_id": gpg_type.id,
    }
    response = admin_client.post(
        f"{api_url_v1}/eda-credentials/", data=data_in
    )
    assert response.status_code == status_code
    assert status_message in response.data.get("inputs.gpg_public_key", "")


@pytest.mark.parametrize(
    ("credential_type", "status_code", "key", "error_message"),
    [
        (
            enums.DefaultCredentialType.VAULT,
            status.HTTP_400_BAD_REQUEST,
            "inputs.vault_password",
            "Cannot be blank",
        ),
        (
            enums.DefaultCredentialType.AAP,
            status.HTTP_400_BAD_REQUEST,
            "inputs.host",
            "Cannot be blank",
        ),
        (
            enums.DefaultCredentialType.GPG,
            status.HTTP_400_BAD_REQUEST,
            "inputs.gpg_public_key",
            "Cannot be blank",
        ),
        (
            # both required and default are True
            enums.DefaultCredentialType.REGISTRY,
            status.HTTP_201_CREATED,
            None,
            None,
        ),
        (
            enums.DefaultCredentialType.SOURCE_CONTROL,
            status.HTTP_201_CREATED,
            None,
            None,
        ),
    ],
)
@pytest.mark.django_db
def test_create_eda_credential_with_empty_inputs_fields(
    admin_client: APIClient,
    preseed_credential_types,
    credential_type,
    status_code,
    key,
    error_message,
):
    credential_type = models.CredentialType.objects.get(name=credential_type)

    data_in = {
        "name": f"eda-credential-{credential_type}",
        "inputs": {},
        "credential_type_id": credential_type.id,
    }
    response = admin_client.post(
        f"{api_url_v1}/eda-credentials/", data=data_in
    )
    assert response.status_code == status_code
    if error_message:
        assert error_message in response.data[key]


@pytest.mark.django_db
def test_retrieve_eda_credential(
    admin_client: APIClient, credential_type: models.CredentialType
):
    obj = models.EdaCredential.objects.create(
        name="eda_credential",
        inputs={"username": "adam", "password": "secret"},
        managed=False,
        credential_type_id=credential_type.id,
    )
    response = admin_client.get(f"{api_url_v1}/eda-credentials/{obj.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "eda_credential"
    assert response.data["inputs"] == {
        "username": "adam",
        "password": "$encrypted$",
    }
    assert response.data["managed"] is False


@pytest.mark.django_db
def test_list_eda_credentials(
    admin_client: APIClient,
    default_scm_credential: models.EdaCredential,
    default_vault_credential: models.EdaCredential,
    managed_registry_credential: models.EdaCredential,
):
    response = admin_client.get(f"{api_url_v1}/eda-credentials/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 2
    assert response.data["results"][0]["name"] == default_scm_credential.name
    assert response.data["results"][1]["name"] == default_vault_credential.name


@pytest.mark.parametrize(
    ("kinds", "expected"),
    [
        ("scm", 1),
        ("registry", 1),
        ("vault", 0),
        ("scm,vault", 1),
        ("scm,registry", 2),
    ],
)
@pytest.mark.django_db
def test_list_eda_credentials_with_kind_filter(
    admin_client: APIClient,
    default_registry_credential: models.EdaCredential,
    default_scm_credential: models.EdaCredential,
    kinds,
    expected,
):
    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?credential_type__kind__in={kinds}"
    )
    assert len(response.data["results"]) == expected


@pytest.mark.django_db
def test_list_eda_credentials_filter_credential_type_id(
    default_registry_credential: models.EdaCredential,
    default_scm_credential: models.EdaCredential,
    admin_client: APIClient,
    preseed_credential_types,
):
    registry_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    scm_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.SOURCE_CONTROL
    )
    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?credential_type_id="
        f"{registry_credential_type.id}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert (
        response.data["results"][0]["credential_type"]["name"]
        == registry_credential_type.name
    )

    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?credential_type_id="
        f"{scm_credential_type.id}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert (
        response.data["results"][0]["credential_type"]["name"]
        == scm_credential_type.name
    )


@pytest.mark.django_db
def test_list_eda_credentials_filter_name(
    default_registry_credential: models.EdaCredential,
    default_scm_credential: models.EdaCredential,
    admin_client: APIClient,
    preseed_credential_types,
):
    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/"
        f"?name={default_registry_credential.name}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert (
        response.data["results"][0]["name"] == default_registry_credential.name
    )

    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?name={default_scm_credential.name}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["name"] == default_scm_credential.name


@pytest.mark.django_db
def test_list_eda_credentials_filter_startswith(
    admin_client: APIClient,
    user_credential_type: models.CredentialType,
    preseed_credential_types,
):
    # NOTE: bulk_create shouldn't be used here because RBAC uses signals which
    # won't update the permissions. If you use bulk_create, you have to call
    # compute_object_role_permissions() to refresh permissions
    # ansible_base.rbac.caching.compute_object_role_permissions
    credential_type_id = user_credential_type.id
    models.EdaCredential.objects.create(
        name="new-credential-1",
        inputs={"sasl_username": "adam", "sasl_password": "secret"},
        credential_type_id=credential_type_id,
    ),
    models.EdaCredential.objects.create(
        name="new-credential-2",
        inputs={"sasl_username": "adam", "sasl_password": "secret"},
        credential_type_id=credential_type_id,
    ),
    models.EdaCredential.objects.create(
        name="new-credential-3",
        inputs={"sasl_username": "adam", "sasl_password": "secret"},
        credential_type_id=credential_type_id,
    ),
    models.EdaCredential.objects.create(
        name="old-credential-1",
        inputs={"sasl_username": "adam", "sasl_password": "secret"},
        credential_type_id=credential_type_id,
    ),

    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?name__istartswith=new-"
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 3

    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?"
        f"credential_type_id={credential_type_id}",
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 4


@pytest.mark.django_db
def test_list_eda_credentials_filter_name_in(
    admin_client: APIClient,
    default_registry_credential: models.EdaCredential,
    default_scm_credential: models.EdaCredential,
    preseed_credential_types,
):
    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?name__in="
        f"{default_registry_credential.name},{default_scm_credential.name}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 2


@pytest.mark.django_db
def test_delete_eda_credential(admin_client: APIClient):
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs={"username": "adam", "password": "secret"},
    )
    response = admin_client.delete(f"{api_url_v1}/eda-credentials/{obj.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert models.EdaCredential.objects.count() == 0


@pytest.mark.django_db
def test_delete_managed_eda_credential(admin_client: APIClient):
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs={"username": "adam", "password": "secret"},
        managed=True,
    )
    response = admin_client.delete(f"{api_url_v1}/eda-credentials/{obj.id}/")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["errors"] == "Managed EDA credential cannot be deleted"
    )


@pytest.mark.django_db
def test_partial_update_eda_credential_without_inputs(
    admin_client: APIClient, credential_type: models.CredentialType
):
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs={"username": "adam", "password": "secret", "key": "private"},
        credential_type_id=credential_type.id,
        managed=True,
    )
    data = {"inputs": {"username": "bearny", "password": "demo"}}
    response = admin_client.patch(
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
def test_partial_update_eda_credential_with_invalid_inputs(
    admin_client: APIClient, credential_type: models.CredentialType
):
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs={"username": "adam", "password": "secret"},
        credential_type_id=credential_type.id,
        managed=True,
    )
    data = {
        "inputs": {
            "username": "bearny",
            "password": "demo",
            "invalid_key": "bad",
        }
    }
    response = admin_client.patch(
        f"{api_url_v1}/eda-credentials/{obj.id}/", data=data
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "Input keys {'invalid_key'} are not defined in the schema"
        in response.data["inputs"][0]
    )


@pytest.mark.parametrize(
    ("credential_type", "inputs"),
    [
        (enums.DefaultCredentialType.VAULT, {}),
        (
            enums.DefaultCredentialType.VAULT,
            {"vault_password": "new_password"},
        ),
        (enums.DefaultCredentialType.AAP, {}),
        (
            enums.DefaultCredentialType.AAP,
            {"host": "new_host", "username": "new user"},
        ),
        (enums.DefaultCredentialType.GPG, {}),
        (enums.DefaultCredentialType.GPG, {"gpg_public_key": DUMMY_GPG_KEY}),
        (enums.DefaultCredentialType.REGISTRY, {}),
        (
            enums.DefaultCredentialType.REGISTRY,
            {"host": "new_host", "username": "new user", "verify_ssl": True},
        ),
        (enums.DefaultCredentialType.SOURCE_CONTROL, {}),
        (
            enums.DefaultCredentialType.SOURCE_CONTROL,
            {"username": "new user", "password": "new password"},
        ),
    ],
)
@pytest.mark.django_db
def test_partial_update_eda_credentials(
    admin_client: APIClient,
    preseed_credential_types,
    credential_type,
    inputs,
):
    old_inputs = {"keep": "data"}
    credential_type = models.CredentialType.objects.get(name=credential_type)
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs=old_inputs,
        credential_type_id=credential_type.id,
    )
    new_name = "new-eda-credential"
    new_description = "new-eda-credential description"
    # update name, description with empty inputs
    data = {"name": new_name, "description": new_description, "inputs": inputs}
    response = admin_client.patch(
        f"{api_url_v1}/eda-credentials/{obj.id}/", data=data
    )
    assert response.status_code == status.HTTP_200_OK
    result = response.data
    assert result["name"] == new_name
    assert result["description"] == new_description

    data = {"inputs": inputs}
    # update inputs
    response = admin_client.patch(
        f"{api_url_v1}/eda-credentials/{obj.id}/", data=data
    )
    result = response.data
    assert result["inputs"]["keep"] == old_inputs["keep"]
    for key in inputs.keys():
        assert result["inputs"][key] is not None


@pytest.mark.django_db
def test_partial_update_eda_credential_with_encrypted_output(
    admin_client: APIClient, credential_type: models.CredentialType
):
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs={"username": "adam", "password": "secret", "key": "private"},
        credential_type_id=credential_type.id,
        managed=True,
    )
    data = {"name": "demo2"}
    response = admin_client.patch(
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
    default_decision_environment: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    eda_credential = default_decision_environment.eda_credential
    response = admin_client.delete(
        f"{api_url_v1}/eda-credentials/{eda_credential.id}/"
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        f"Credential {eda_credential.name} is being referenced by other "
        "resources and cannot be deleted"
    ) in response.data["detail"]


@pytest.mark.django_db
def test_delete_credential_with_project_reference(
    default_project: models.Project,
    admin_client: APIClient,
    preseed_credential_types,
):
    eda_credential = default_project.eda_credential
    response = admin_client.delete(
        f"{api_url_v1}/eda-credentials/{eda_credential.id}/"
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        f"Credential {eda_credential.name} is being referenced by other "
        "resources and cannot be deleted"
    ) in response.data["detail"]


@pytest.mark.django_db
def test_delete_credential_with_activation_reference(
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    eda_credential = default_activation.eda_credentials.all()[0]
    response = admin_client.delete(
        f"{api_url_v1}/eda-credentials/{eda_credential.id}/"
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        f"Credential {eda_credential.name} is being referenced by other "
        "resources and cannot be deleted"
    ) in response.data["detail"]


@pytest.mark.django_db
def test_delete_credential_used_by_activation_forced(
    default_activation: models.Activation,
    admin_client: APIClient,
    preseed_credential_types,
):
    eda_credential = default_activation.eda_credentials.all()[0]
    response = admin_client.delete(
        f"{api_url_v1}/eda-credentials/{eda_credential.id}/?force=true",
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert default_activation.eda_credentials.count() == 0


@pytest.mark.django_db
def test_delete_credential_used_by_project_with_gpg_credential(
    admin_client: APIClient,
    preseed_credential_types,
):
    gpg_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.GPG
    )
    eda_credential = models.EdaCredential.objects.create(
        name="test_gpg_credential",
        inputs={"gpg_public_key": "secret"},
        credential_type=gpg_credential_type,
    )
    models.Project.objects.create(
        name="default-project",
        description="Default Project",
        url="https://git.example.com/acme/project-01",
        git_hash="684f62df18ce5f8d5c428e53203b9b975426eed0",
        signature_validation_credential=eda_credential,
        scm_branch="main",
        proxy="http://user:secret@myproxy.com",
        import_state=models.Project.ImportState.COMPLETED,
        import_task_id="c8a7a0e3-05e7-4376-831a-6b8af80107bd",
    )
    response = admin_client.delete(
        f"{api_url_v1}/eda-credentials/{eda_credential.id}/",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        f"Credential {eda_credential.name} is being referenced by other "
        "resources and cannot be deleted"
    ) in response.data["detail"]


@pytest.mark.parametrize("refs", ["true", "false"])
@pytest.mark.django_db
def test_retrieve_eda_credential_with_refs(
    default_activation: models.Activation,
    admin_client: APIClient,
    refs,
    preseed_credential_types,
):
    eda_credential = default_activation.eda_credentials.all()[0]

    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/{eda_credential.id}/?refs={refs}",
    )
    assert response.status_code == status.HTTP_200_OK

    if refs == "true":
        assert response.data["references"] is not None
        references = response.data["references"]

        assert len(references) == 1
        references[0] = {
            "type": "Activation",
            "id": default_activation.id,
            "name": default_activation.name,
            "url": f"api/eda/v1/activations/{default_activation.id}/",
        }
    else:
        assert response.data["references"] is None


@pytest.mark.django_db
def test_retrieve_eda_credential_with_empty_encrypted_fields(
    admin_client: APIClient, preseed_credential_types
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
    response = admin_client.post(
        f"{api_url_v1}/eda-credentials/", data=data_in
    )
    assert response.status_code == status.HTTP_201_CREATED
    key_list = list(response.data["inputs"].keys())
    assert "ssh_key_unlock" not in key_list
    assert key_list[0] == "username"
    assert key_list[1] == "password"
