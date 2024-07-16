from typing import Any, Dict

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import enums, models
from aap_eda.core.utils.credentials import inputs_to_store
from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_list_decision_environments(
    default_decision_environment: models.DecisionEnvironment,
    admin_client: APIClient,
):
    response = admin_client.get(f"{api_url_v1}/decision-environments/")
    assert response.status_code == status.HTTP_200_OK
    result = response.data["results"][0]
    assert_de_base_data(result, default_decision_environment)
    assert_de_fk_data(result, default_decision_environment)


@pytest.mark.parametrize(
    ("credential_type", "status_code", "status_message"),
    [
        (
            enums.DefaultCredentialType.VAULT,
            status.HTTP_400_BAD_REQUEST,
            "The type of credential can only be one of ['Container Registry']",
        ),
        (
            enums.DefaultCredentialType.AAP,
            status.HTTP_400_BAD_REQUEST,
            "The type of credential can only be one of ['Container Registry']",
        ),
        (
            enums.DefaultCredentialType.GPG,
            status.HTTP_400_BAD_REQUEST,
            "The type of credential can only be one of ['Container Registry']",
        ),
        (
            enums.DefaultCredentialType.SOURCE_CONTROL,
            status.HTTP_400_BAD_REQUEST,
            "The type of credential can only be one of ['Container Registry']",
        ),
        (
            enums.DefaultCredentialType.REGISTRY,
            status.HTTP_201_CREATED,
            None,
        ),
    ],
)
@pytest.mark.django_db
def test_create_decision_environment(
    default_registry_credential: models.EdaCredential,
    default_organization: models.Organization,
    admin_client: APIClient,
    preseed_credential_types,
    credential_type,
    status_code,
    status_message,
):
    credential_type = models.CredentialType.objects.get(name=credential_type)
    credential = models.EdaCredential.objects.create(
        name="eda-credential",
        description="Default Credential",
        credential_type=credential_type,
        inputs=inputs_to_store(
            {
                "username": "dummy-user",
                "password": "dummy-password",
                "host": "registry.com",
            }
        ),
    )
    data_in = {
        "name": "de1",
        "description": "desc here",
        "image_url": "registry.com/img1:tag1",
        "organization_id": default_organization.id,
        "eda_credential_id": credential.id,
    }
    response = admin_client.post(
        f"{api_url_v1}/decision-environments/", data=data_in
    )
    assert response.status_code == status_code
    if status_code == status.HTTP_201_CREATED:
        id_ = response.data["id"]
        result = response.data
        result.pop("created_at")
        result.pop("modified_at")
        assert result == {"id": id_, **data_in}
        assert models.DecisionEnvironment.objects.filter(pk=id_).exists()
    else:
        assert status_message in response.data["eda_credential_id"]


@pytest.mark.parametrize(
    ("credential_inputs", "status_code", "status_message"),
    [
        (
            {"host": "quay.io"},
            status.HTTP_400_BAD_REQUEST,
            "Need username and password or just token in credential",
        ),
        (
            {"host": "quay.io", "username": "fred"},
            status.HTTP_400_BAD_REQUEST,
            "Need username and password or just token in credential",
        ),
        (
            {"host": "quay.io", "password": "token1"},
            status.HTTP_400_BAD_REQUEST,
            "does not match with the credential host",
        ),
        (
            {"username": "Fred", "password": "token1"},
            status.HTTP_400_BAD_REQUEST,
            "needs to have host information",
        ),
        (
            {"host": "registry.com", "password": "token1"},
            status.HTTP_201_CREATED,
            "",
        ),
    ],
)
@pytest.mark.django_db
def test_create_decision_environment_with_empty_credential(
    default_registry_credential: models.EdaCredential,
    default_organization: models.Organization,
    admin_client: APIClient,
    preseed_credential_types,
    credential_inputs,
    status_code,
    status_message,
):
    credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    credential = models.EdaCredential.objects.create(
        name="eda-credential",
        description="Default Credential",
        credential_type=credential_type,
        inputs=inputs_to_store(credential_inputs),
    )
    data_in = {
        "name": "de1",
        "description": "desc here",
        "image_url": "registry.com/img1:tag1",
        "organization_id": default_organization.id,
        "eda_credential_id": credential.id,
    }
    response = admin_client.post(
        f"{api_url_v1}/decision-environments/", data=data_in
    )
    assert response.status_code == status_code
    if status_message:
        errors = response.data.get("eda_credential_id") or response.data.get(
            "non_field_errors"
        )
        assert status_message in str(errors)


@pytest.mark.django_db
def test_create_decision_environment_bad_ids(admin_client: APIClient):
    bad_ids = [
        {"organization_id": 3000001},
        {"eda_credential_id": 3000001},
    ]
    data_in = {
        "name": "de1",
        "description": "desc here",
        "image_url": "registry.com/img1:tag1",
    }
    for bad_id in bad_ids:
        response = admin_client.post(
            f"{api_url_v1}/decision-environments/", data=data_in | bad_id
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "id 3000001 does not exist" in str(response.json())


@pytest.mark.django_db
def test_retrieve_decision_environment(
    default_decision_environment: models.DecisionEnvironment,
    admin_client: APIClient,
):
    response = admin_client.get(
        f"{api_url_v1}/decision-environments/"
        f"{default_decision_environment.id}/"
    )
    assert response.status_code == status.HTTP_200_OK

    assert_de_base_data(response.data, default_decision_environment)
    assert_de_related_data(response.data, default_decision_environment)


@pytest.mark.django_db
def test_retrieve_decision_environment_not_exist(admin_client: APIClient):
    response = admin_client.get(f"{api_url_v1}/decision-environments/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize(
    ("credential_type", "status_code", "status_message"),
    [
        (
            enums.DefaultCredentialType.VAULT,
            status.HTTP_400_BAD_REQUEST,
            "The type of credential can only be one of ['Container Registry']",
        ),
        (
            enums.DefaultCredentialType.AAP,
            status.HTTP_400_BAD_REQUEST,
            "The type of credential can only be one of ['Container Registry']",
        ),
        (
            enums.DefaultCredentialType.GPG,
            status.HTTP_400_BAD_REQUEST,
            "The type of credential can only be one of ['Container Registry']",
        ),
        (
            enums.DefaultCredentialType.SOURCE_CONTROL,
            status.HTTP_400_BAD_REQUEST,
            "The type of credential can only be one of ['Container Registry']",
        ),
        (
            enums.DefaultCredentialType.REGISTRY,
            status.HTTP_200_OK,
            None,
        ),
    ],
)
@pytest.mark.django_db
def test_partial_update_decision_environment(
    default_decision_environment: models.DecisionEnvironment,
    admin_client: APIClient,
    preseed_credential_types,
    credential_type,
    status_code,
    status_message,
):
    credential_type = models.CredentialType.objects.get(name=credential_type)
    credential = models.EdaCredential.objects.create(
        name="eda-credential",
        description="Default Credential",
        credential_type=credential_type,
        inputs=inputs_to_store(
            {
                "username": "dummy-user",
                "password": "dummy-password",
                "host": "quay.io",
            }
        ),
    )
    data = {"eda_credential_id": credential.id}
    response = admin_client.patch(
        f"{api_url_v1}/decision-environments/"
        f"{default_decision_environment.id}/",
        data=data,
    )
    assert response.status_code == status_code
    if status_message:
        assert status_message in response.data["eda_credential_id"]


@pytest.mark.parametrize(
    ("inputs", "status_code", "status_message"),
    [
        (
            {
                "username": "dummy-user",
                "password": "secret",
                "host": "quay.io",
            },
            status.HTTP_200_OK,
            None,
        ),
        (
            {
                "username": "dummy-user",
                "password": "secret",
                "host": "registry.com",
            },
            status.HTTP_400_BAD_REQUEST,
            "does not match with the credential host",
        ),
    ],
)
@pytest.mark.django_db
def test_partial_update_decision_environment_with_image_url_and_host(
    default_decision_environment: models.DecisionEnvironment,
    admin_client: APIClient,
    preseed_credential_types,
    inputs,
    status_code,
    status_message,
):
    credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    credential = models.EdaCredential.objects.create(
        name="eda-credential",
        description="Default Credential",
        credential_type=credential_type,
        inputs=inputs_to_store(inputs),
    )
    data = {"eda_credential_id": credential.id, "image_url": "quay.io"}
    response = admin_client.patch(
        f"{api_url_v1}/decision-environments/"
        f"{default_decision_environment.id}/",
        data=data,
    )
    assert response.status_code == status_code
    if status_message:
        errors = response.data.get("eda_credential_id") or response.data.get(
            "non_field_errors"
        )
        assert status_message in str(errors)


@pytest.mark.django_db
def test_partial_update_decision_environment_bad_ids(
    default_decision_environment: models.DecisionEnvironment,
    admin_client: APIClient,
):
    bad_ids = [
        {"organization_id": 3000001},
        {"eda_credential_id": 3000001},
    ]
    for bad_id in bad_ids:
        response = admin_client.patch(
            f"{api_url_v1}/decision-environments/"
            f"{default_decision_environment.id}/",
            data=bad_id,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "id 3000001 does not exist" in str(response.json())


@pytest.mark.django_db
def test_delete_decision_environment_conflict(
    default_decision_environment: models.DecisionEnvironment,
    default_activation: models.Activation,
    admin_client: APIClient,
):
    response = admin_client.delete(
        f"{api_url_v1}/decision-environments/"
        f"{default_decision_environment.id}/"
    )
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_delete_decision_environment_success(
    default_decision_environment: models.DecisionEnvironment,
    admin_client: APIClient,
):
    response = admin_client.delete(
        f"{api_url_v1}/decision-environments/"
        f"{default_decision_environment.id}/"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert (
        models.DecisionEnvironment.objects.filter(
            pk=int(default_decision_environment.id)
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_delete_decision_environment_force(
    default_activation: models.Activation, admin_client: APIClient
):
    de_id = default_activation.decision_environment.id
    response = admin_client.delete(
        f"{api_url_v1}/decision-environments/{de_id}/?force=True"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert (
        models.DecisionEnvironment.objects.filter(pk=int(de_id)).count() == 0
    )
    default_activation.refresh_from_db()
    assert default_activation.decision_environment is None


# UTILS
# ------------------------------

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def assert_de_base_data(
    response: Dict[str, Any], expected: models.DecisionEnvironment
):
    assert response["id"] == expected.id
    assert response["name"] == expected.name
    assert response["description"] == expected.description
    assert response["image_url"] == expected.image_url
    assert response["created_at"] == expected.created_at.strftime(
        DATETIME_FORMAT
    )
    assert response["modified_at"] == expected.modified_at.strftime(
        DATETIME_FORMAT
    )


def assert_de_fk_data(
    response: Dict[str, Any], expected: models.DecisionEnvironment
):
    if expected.eda_credential:
        assert response["eda_credential_id"] == expected.eda_credential.id
    else:
        assert not response["eda_credential_id"]
    if expected.organization:
        assert response["organization_id"] == expected.organization.id
    else:
        assert not response["organization_id"]


def assert_de_related_data(response: Dict[str, Any], expected: models.Project):
    if expected.eda_credential:
        credential_data = response["eda_credential"]
        assert credential_data["id"] == expected.eda_credential.id
        assert credential_data["name"] == expected.eda_credential.name
        assert (
            credential_data["description"]
            == expected.eda_credential.description
        )
        assert credential_data["managed"] == expected.eda_credential.managed
        assert (
            credential_data["credential_type_id"]
            == expected.eda_credential.credential_type.id
        )
    else:
        assert not response["eda_credential"]
    if expected.organization:
        organization_data = response["organization"]
        assert organization_data["id"] == expected.organization.id
        assert organization_data["name"] == expected.organization.name
        assert (
            organization_data["description"]
            == expected.organization.description
        )
    else:
        assert not response["organization"]
