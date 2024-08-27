from pathlib import Path

import pytest
import yaml
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import enums, models
from aap_eda.core.utils.credentials import ENCRYPTED_STRING, inputs_to_store
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

NEW_GPG_KEY = """
-----BEGIN PGP PUBLIC KEY BLOCK-----

mDMEZgM6UhYJKwYBBAHaRw8BAQdA0cqUu52nNKjOalIDfszBQvWs0RwRZ/Q5VZYV
L3sMjim0HEJpbGwgV2VpIDxiaWx3ZWlAcmVkaGF0LmNvbT6IkwQTFgoAOxYhBP5A
Fih9tcPiGRc5ZN56Xu/6KHulBQJmAzpSAhsDBQsJCAcCAiICBhUKCQgLAgQWAgMB
Ah4HAheAAAoJEN56Xu/6KHulM8oA/j543Q3ihrwuk7wCtMJmv16UheIPnSe8WNJ6
5KxOqr3CAPsFA6CGdoRL274WVGi3qtq9ZrUMlbKR9UckXnnAN9cBCLg4BGYDOlIS
CisGAQQBl1UBBQEBB0BrB8weyP0inQ/85HhDMd0ZM0UITMSMcS2stT2jZxyobgMB
CAeIeAQYFgoAIBYhBP5AFih9tcPiGRc5ZN56Xu/6KHulBQJmAzpSAhsMAAoJEN56
Xu/6KHulB18A/Rx2NwI44yCqh59Nl4r/FIdvrdoBRROlhpIdlqWYeMx7AQCeVK5H
TqoAVpLewW7aUe1XcxZQ7gpUtnnIDu1XlqiWAw==
=fP3q
-----END PGP PUBLIC KEY BLOCK-----
"""

DUMMY_SSH_KEY = """
-----BEGIN OPENSSH PRIVATE KEY-----
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
hzhhV19kdlZMmjYxQUE2POfyeBw=
-----END OPENSSH PRIVATE KEY-----
"""


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
    default_organization: models.Organization,
    inputs,
    status_code,
    status_message,
):
    data_in = {
        "name": "eda-credential",
        "inputs": inputs,
        "credential_type_id": credential_type.id,
        "organization_id": default_organization.id,
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


@pytest.mark.django_db
def test_create_eda_credential_with_none_credential_type(
    admin_client: APIClient,
    default_organization: models.Organization,
):
    data = "secret"
    data_in = {
        "name": "eda-credential",
        "inputs": {"username": "adam", "password": data},
        "credential_type_id": None,
        "organization_id": default_organization.id,
    }
    response = admin_client.post(
        f"{api_url_v1}/eda-credentials/", data=data_in
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "This field may not be null." in response.data["credential_type_id"]


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
            "No valid GPG data found",
        ),
    ],
)
@pytest.mark.django_db
def test_create_eda_credential_with_gpg_key_data(
    admin_client: APIClient,
    default_organization: models.Organization,
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
        "organization_id": default_organization.id,
    }
    response = admin_client.post(
        f"{api_url_v1}/eda-credentials/", data=data_in
    )
    assert response.status_code == status_code
    if response.data.get("inputs.gpg_public_key"):
        message = response.data.get("inputs.gpg_public_key")[0]
        assert message.startswith(status_message)


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
    default_organization: models.Organization,
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
        "organization_id": default_organization.id,
    }
    response = admin_client.post(
        f"{api_url_v1}/eda-credentials/", data=data_in
    )
    assert response.status_code == status_code
    if error_message:
        assert error_message in response.data[key]


@pytest.mark.django_db
def test_retrieve_eda_credential(
    admin_client: APIClient,
    credential_type: models.CredentialType,
    default_organization: models.Organization,
):
    obj = models.EdaCredential.objects.create(
        name="eda_credential",
        inputs={"username": "adam", "password": "secret"},
        managed=False,
        credential_type_id=credential_type.id,
        organization=default_organization,
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


@pytest.mark.django_db
def test_list_eda_credentials_with_kind_filter(
    admin_client: APIClient,
    default_registry_credential: models.EdaCredential,
    default_scm_credential: models.EdaCredential,
):
    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?credential_type__kind=scm"
    )
    assert len(response.data["results"]) == 1

    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?credential_type__kind=registry"
    )
    assert len(response.data["results"]) == 1

    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?credential_type__kind=vault"
    )
    assert len(response.data["results"]) == 0

    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?credential_type__kind=scm"
        "&credential_type__kind=vault",
    )
    assert len(response.data["results"]) == 1

    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?credential_type__kind=scm"
        "&credential_type__kind=registry",
    )
    assert len(response.data["results"]) == 2

    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?"
        "credential_type__kind__in=scm,registry",
    )
    assert len(response.data["results"]) == 2

    name_prefix = default_registry_credential.name[0]
    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?credential_type__kind=scm"
        f"&credential_type__kind=registry&name={name_prefix}",
    )
    assert len(response.data["results"]) == 1


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
def test_delete_eda_credential(
    admin_client: APIClient, default_organization: models.Organization
):
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs={"username": "adam", "password": "secret"},
        organization=default_organization,
    )
    response = admin_client.delete(f"{api_url_v1}/eda-credentials/{obj.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert models.EdaCredential.objects.count() == 0


@pytest.mark.django_db
def test_delete_managed_eda_credential(
    admin_client: APIClient,
    default_organization: models.Organization,
):
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs={"username": "adam", "password": "secret"},
        managed=True,
        organization=default_organization,
    )
    response = admin_client.delete(f"{api_url_v1}/eda-credentials/{obj.id}/")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["errors"] == "Managed EDA credential cannot be deleted"
    )


@pytest.mark.django_db
def test_partial_update_eda_credential_without_inputs(
    admin_client: APIClient,
    credential_type: models.CredentialType,
    default_organization: models.Organization,
):
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs={"username": "adam", "password": "secret"},
        credential_type_id=credential_type.id,
        managed=True,
        organization=default_organization,
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
    }


@pytest.mark.django_db
def test_partial_update_eda_credential_with_invalid_inputs(
    admin_client: APIClient,
    credential_type: models.CredentialType,
    default_organization: models.Organization,
):
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs={"username": "adam", "password": "secret"},
        credential_type_id=credential_type.id,
        managed=True,
        organization=default_organization,
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
    ("credential_type", "old_inputs", "inputs", "expected_inputs"),
    [
        (
            enums.DefaultCredentialType.VAULT,
            {"vault_password": "password", "vault_id": "test"},
            {"vault_password": "new_password"},
            {"vault_password": ENCRYPTED_STRING, "vault_id": "test"},
        ),
        (
            enums.DefaultCredentialType.VAULT,
            {"vault_password": "password", "vault_id": "test"},
            {"vault_id": "new_id"},
            {"vault_password": ENCRYPTED_STRING, "vault_id": "new_id"},
        ),
        (
            enums.DefaultCredentialType.AAP,
            {
                "host": "host",
                "username": "user name",
                "password": "password",
                "oauth_token": "token",
                "verify_ssl": True,
            },
            {
                "host": "new host",
                "verify_ssl": False,
            },
            {
                "host": "new host",
                "username": "user name",
                "password": ENCRYPTED_STRING,
                "oauth_token": ENCRYPTED_STRING,
                "verify_ssl": False,
            },
        ),
        (
            enums.DefaultCredentialType.AAP,
            {
                "host": "host",
                "username": "user name",
                "password": "password",
                "oauth_token": "token",
                "verify_ssl": True,
            },
            {
                "password": "new password",
                "oauth_token": "new token",
                "verify_ssl": False,
            },
            {
                "host": "host",
                "username": "user name",
                "password": ENCRYPTED_STRING,
                "oauth_token": ENCRYPTED_STRING,
                "verify_ssl": False,
            },
        ),
        (
            enums.DefaultCredentialType.GPG,
            {"gpg_public_key": DUMMY_GPG_KEY},
            {"gpg_public_key": NEW_GPG_KEY},
            {"gpg_public_key": ENCRYPTED_STRING},
        ),
        (
            enums.DefaultCredentialType.GPG,
            {"gpg_public_key": DUMMY_GPG_KEY},
            {},
            {"gpg_public_key": ENCRYPTED_STRING},
        ),
        (
            enums.DefaultCredentialType.REGISTRY,
            {
                "host": "host",
                "username": "user name",
                "password": "password",
                "verify_ssl": True,
            },
            {
                "host": "new host",
                "username": "new user name",
                "verify_ssl": False,
            },
            {
                "host": "new host",
                "username": "new user name",
                "password": ENCRYPTED_STRING,
                "verify_ssl": False,
            },
        ),
        (
            enums.DefaultCredentialType.REGISTRY,
            {
                "host": "host",
                "username": "user name",
                "password": "password",
                "verify_ssl": True,
            },
            {
                "host": "new host",
                "username": "new user name",
                "password": "password",
            },
            {
                "host": "new host",
                "username": "new user name",
                "password": ENCRYPTED_STRING,
                "verify_ssl": True,
            },
        ),
        (
            enums.DefaultCredentialType.SOURCE_CONTROL,
            {
                "username": "user name",
                "password": "password",
                "ssh_key_data": DUMMY_SSH_KEY,
                "ssh_key_unlock": "secret",
            },
            {},
            {
                "username": "user name",
                "password": ENCRYPTED_STRING,
                "ssh_key_data": ENCRYPTED_STRING,
                "ssh_key_unlock": ENCRYPTED_STRING,
            },
        ),
        (
            enums.DefaultCredentialType.SOURCE_CONTROL,
            {
                "username": "user name",
                "password": "password",
                "ssh_key_data": DUMMY_SSH_KEY,
                "ssh_key_unlock": "secret",
            },
            {
                "username": "new user name",
                "ssh_key_unlock": "new lock",
            },
            {
                "username": "new user name",
                "password": ENCRYPTED_STRING,
                "ssh_key_data": ENCRYPTED_STRING,
                "ssh_key_unlock": ENCRYPTED_STRING,
            },
        ),
    ],
)
@pytest.mark.django_db
def test_partial_update_eda_credentials(
    admin_client: APIClient,
    default_organization: models.Organization,
    preseed_credential_types,
    credential_type,
    old_inputs,
    inputs,
    expected_inputs,
):
    credential_type = models.CredentialType.objects.get(name=credential_type)
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs=inputs_to_store(old_inputs),
        credential_type_id=credential_type.id,
        organization=default_organization,
    )
    new_name = "new-eda-credential"
    new_description = "new-eda-credential description"
    # update name, description with empty inputs
    data = {"name": new_name, "description": new_description}
    response = admin_client.patch(
        f"{api_url_v1}/eda-credentials/{obj.id}/", data=data
    )
    assert response.status_code == status.HTTP_200_OK
    result = response.data
    assert result["name"] == new_name
    assert result["description"] == new_description
    for key in old_inputs.keys():
        assert result["inputs"][key] is not None

    data = {"inputs": inputs}
    # update inputs
    response = admin_client.patch(
        f"{api_url_v1}/eda-credentials/{obj.id}/", data=data
    )
    result = response.data
    for key in expected_inputs.keys():
        assert result["inputs"][key] == expected_inputs[key]

    obj.refresh_from_db()
    obj_inputs = yaml.safe_load(obj.inputs.get_secret_value())

    # assert the inputs are really updated
    for key in inputs.keys():
        assert obj_inputs[key] == inputs[key]

    # assert other inputs fields are not updated
    for key in [key for key in old_inputs if key not in inputs]:
        assert obj_inputs[key] == old_inputs[key]


@pytest.mark.django_db
def test_partial_update_eda_credential_with_encrypted_output(
    admin_client: APIClient,
    credential_type: models.CredentialType,
    default_organization: models.Organization,
):
    obj = models.EdaCredential.objects.create(
        name="eda-credential",
        inputs={"username": "adam", "password": "secret"},
        credential_type_id=credential_type.id,
        managed=True,
        organization=default_organization,
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
    }
    assert result["name"] == "demo2"


@pytest.mark.django_db
def test_partial_update_scm_credential_with_encrypted_output(
    admin_client: APIClient,
    default_organization: models.Organization,
    preseed_credential_types,
):
    scm_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.SOURCE_CONTROL
    )
    key_file = DATA_DIR / "demo1"
    with open(key_file) as f:
        key_data = f.read()

    inputs = {"ssh_key_data": key_data, "ssh_key_unlock": "password"}

    data_in = {
        "name": "eda-credential",
        "inputs": inputs,
        "credential_type_id": scm_credential_type.id,
        "organization_id": default_organization.id,
    }
    response = admin_client.post(
        f"{api_url_v1}/eda-credentials/", data=data_in
    )
    assert response.status_code == status.HTTP_201_CREATED
    obj = response.json()

    inputs = {"ssh_key_data": key_data}

    data = {}
    data["description"] = "new desc"
    data["inputs"] = inputs
    data["credential_type_id"] = scm_credential_type.id
    data["organization_id"] = default_organization.id

    response = admin_client.patch(
        f"{api_url_v1}/eda-credentials/{obj['id']}/", data=data
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["description"] == "new desc"
    result = response.data
    assert result["inputs"] == {
        "ssh_key_data": ENCRYPTED_STRING,
        "ssh_key_unlock": ENCRYPTED_STRING,
    }


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
def test_delete_credential_with_event_stream_reference(
    default_event_stream: models.EventStream,
    admin_client: APIClient,
    preseed_credential_types,
):
    eda_credential = default_event_stream.eda_credential
    for url in [
        f"{api_url_v1}/eda-credentials/{eda_credential.id}/",
        f"{api_url_v1}/eda-credentials/{eda_credential.id}/?force=true",
    ]:
        response = admin_client.delete(url)
        assert response.status_code == status.HTTP_409_CONFLICT
        assert (
            f"Credential {eda_credential.name} is being referenced by some "
            "event streams and cannot be deleted. "
            "Please delete the EventStream(s) first"
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
    default_organization,
    preseed_credential_types,
):
    gpg_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.GPG
    )
    eda_credential = models.EdaCredential.objects.create(
        name="test_gpg_credential",
        inputs={"gpg_public_key": "secret"},
        credential_type=gpg_credential_type,
        organization=default_organization,
    )
    models.Project.objects.create(
        name="default-project",
        description="Default Project",
        url="https://git.example.com/acme/project-01",
        organization=default_organization,
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
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
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
        "organization_id": default_organization.id,
    }
    response = admin_client.post(
        f"{api_url_v1}/eda-credentials/", data=data_in
    )
    assert response.status_code == status.HTTP_201_CREATED
    keys = response.data["inputs"].keys()
    assert "ssh_key_unlock" not in keys
    assert "username" in keys
    assert "password" in keys
