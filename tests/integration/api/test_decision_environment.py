from typing import Any, Dict

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_list_decision_environments(
    default_de: models.DecisionEnvironment, client: APIClient
):
    response = client.get(f"{api_url_v1}/decision-environments/")
    assert response.status_code == status.HTTP_200_OK
    result = response.data["results"][0]
    assert_de_base_data(result, default_de)
    assert_de_fk_data(result, default_de)


@pytest.mark.django_db
def test_create_decision_environment(
    default_eda_credential: models.EdaCredential,
    default_organization: models.Organization,
    client: APIClient,
):
    data_in = {
        "name": "de1",
        "description": "desc here",
        "image_url": "registry.com/img1:tag1",
        "organization_id": default_organization.id,
        "eda_credential_id": default_eda_credential.id,
    }
    response = client.post(
        f"{api_url_v1}/decision-environments/", data=data_in
    )
    assert response.status_code == status.HTTP_201_CREATED
    id_ = response.data["id"]
    result = response.data
    result.pop("created_at")
    result.pop("modified_at")
    assert result == {"id": id_, **data_in}
    assert models.DecisionEnvironment.objects.filter(pk=id_).exists()


@pytest.mark.django_db
def test_retrieve_decision_environment(
    default_de: models.DecisionEnvironment, client: APIClient
):
    response = client.get(
        f"{api_url_v1}/decision-environments/{default_de.id}/"
    )
    assert response.status_code == status.HTTP_200_OK

    assert_de_base_data(response.data, default_de)
    assert_de_related_data(response.data, default_de)


@pytest.mark.django_db
def test_retrieve_decision_environment_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/decision-environments/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_partial_update_decision_environment(
    default_de: models.DecisionEnvironment,
    default_vault_credential: models.EdaCredential,
    client: APIClient,
):
    data = {"eda_credential_id": default_vault_credential.id}
    response = client.patch(
        f"{api_url_v1}/decision-environments/{default_de.id}/", data=data
    )
    assert response.status_code == status.HTTP_200_OK

    default_de.refresh_from_db()
    assert_de_base_data(response.data, default_de)
    assert_de_fk_data(response.data, default_de)

    assert default_de.eda_credential == default_vault_credential


@pytest.mark.django_db
def test_delete_decision_environment_conflict(
    default_de: models.DecisionEnvironment,
    default_activation: models.Activation,
    client: APIClient,
):
    response = client.delete(
        f"{api_url_v1}/decision-environments/{default_de.id}/"
    )
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_delete_decision_environment_success(
    default_de: models.DecisionEnvironment, client: APIClient
):
    response = client.delete(
        f"{api_url_v1}/decision-environments/{default_de.id}/"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert (
        models.DecisionEnvironment.objects.filter(
            pk=int(default_de.id)
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_delete_decision_environment_force(
    default_activation: models.Activation, client: APIClient
):
    de_id = default_activation.decision_environment.id
    response = client.delete(
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
