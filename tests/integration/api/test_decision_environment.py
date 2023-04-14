import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_list_decision_environments(client: APIClient):
    credential = models.Credential.objects.create(
        name="credential1", username="me", secret="sec1"
    )
    obj = models.DecisionEnvironment.objects.create(
        name="de1", image_url="registry.com/img1:tag1", credential=credential
    )
    response = client.get(f"{api_url_v1}/decision-environments/")
    assert response.status_code == status.HTTP_200_OK
    result = response.data["results"][0]
    result.pop("created_at")
    result.pop("modified_at")
    assert result == {
        "name": "de1",
        "description": "",
        "image_url": "registry.com/img1:tag1",
        "credential_id": credential.id,
        "id": obj.id,
    }


@pytest.mark.django_db
def test_create_decision_environment(client: APIClient):
    credential = models.Credential.objects.create(
        name="credential1", username="me", secret="sec1"
    )
    data_in = {
        "name": "de1",
        "description": "desc here",
        "image_url": "registry.com/img1:tag1",
        "credential_id": credential.id,
    }
    response = client.post(
        f"{api_url_v1}/decision-environments/", data=data_in
    )
    assert response.status_code == status.HTTP_201_CREATED
    id_ = response.data["id"]
    result = response.data
    result.pop("created_at")
    result.pop("modified_at")
    assert result == {
        "name": "de1",
        "description": "desc here",
        "image_url": "registry.com/img1:tag1",
        "credential_id": credential.id,
        "id": id_,
    }
    assert models.DecisionEnvironment.objects.filter(pk=id_).exists()


@pytest.mark.django_db
def test_retrieve_decision_environment(client: APIClient):
    credential = models.Credential.objects.create(
        name="credential1", username="me", secret="sec1"
    )
    obj = models.DecisionEnvironment.objects.create(
        name="de1", image_url="registry.com/img1:tag1", credential=credential
    )
    response = client.get(f"{api_url_v1}/decision-environments/{obj.id}/")
    assert response.status_code == status.HTTP_200_OK
    result = response.data
    result.pop("created_at")
    result.pop("modified_at")
    assert result == {
        "id": obj.id,
        "name": "de1",
        "description": "",
        "image_url": "registry.com/img1:tag1",
        "credential": {
            "id": credential.id,
            "name": credential.name,
            "description": credential.description,
            "credential_type": credential.credential_type.value,
            "username": credential.username,
        },
    }


@pytest.mark.django_db
def test_retrieve_decision_environment_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/decision-environments/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_partial_update_decision_environment(client: APIClient):
    obj = models.DecisionEnvironment.objects.create(
        name="de1", image_url="registry.com/img1:tag1"
    )
    credential = models.Credential.objects.create(
        name="credential1", username="me", secret="sec1"
    )
    data = {"credential_id": credential.id}
    response = client.patch(
        f"{api_url_v1}/decision-environments/{obj.id}/", data=data
    )
    assert response.status_code == status.HTTP_200_OK
    result = response.data
    result.pop("created_at")
    result.pop("modified_at")
    assert result == {
        "name": "de1",
        "description": "",
        "image_url": "registry.com/img1:tag1",
        "credential_id": credential.id,
        "id": obj.id,
    }
    updated_obj = models.DecisionEnvironment.objects.filter(pk=obj.id).first()
    assert updated_obj.credential == credential


@pytest.mark.django_db
def test_delete_decision_environment(client: APIClient):
    obj = models.DecisionEnvironment.objects.create(
        name="de1", image_url="registry.com/img1:tag1"
    )
    response = client.delete(f"{api_url_v1}/decision-environments/{obj.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert models.DecisionEnvironment.objects.filter(pk=obj.id).count() == 0
