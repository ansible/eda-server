import pytest
import yaml
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.api.serializers.project import ENCRYPTED_STRING
from aap_eda.core import models
from tests.integration.constants import api_url_v1


def converted_extra_var(var: str) -> str:
    return yaml.safe_dump(yaml.safe_load(var))


@pytest.mark.django_db
def test_list_extra_var(client: APIClient, default_extra_var):
    response = client.get(f"{api_url_v1}/extra-vars/")
    assert response.status_code == status.HTTP_200_OK
    data = response.data["results"][0]
    assert_extra_var_data(data, default_extra_var)


@pytest.mark.django_db
def test_create_extra_var(client: APIClient, extra_var_data: str):
    data_in = {
        "extra_var": extra_var_data,
    }
    response = client.post(f"{api_url_v1}/extra-vars/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    id_ = response.data["id"]
    assert response.data["extra_var"] == converted_extra_var(TEST_EXTRA_VAR)
    assert models.ExtraVar.objects.filter(pk=id_).exists()


@pytest.mark.django_db
def test_create_vault_extra_var(client: APIClient, vault_extra_var_data: str):
    data_in = {
        "extra_var": vault_extra_var_data,
    }
    response = client.post(f"{api_url_v1}/extra-vars/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    id = response.data["id"]
    assert response.data["extra_var"] == f"limit: {ENCRYPTED_STRING}\n"
    assert models.ExtraVar.objects.filter(pk=id).exists()
    assert models.ExtraVar.objects.first().extra_var == vault_extra_var_data


@pytest.mark.django_db
def test_retrieve_extra_var(client: APIClient, default_extra_var: str):
    response = client.get(f"{api_url_v1}/extra-vars/{default_extra_var.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert_extra_var_data(response.data, default_extra_var)


@pytest.mark.django_db
def test_retrieve_vault_extra_var(client: APIClient):
    obj = models.ExtraVar.objects.create(extra_var=TEST_VAULT_EXTRA_VAR)
    response = client.get(f"{api_url_v1}/extra-vars/{obj.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["extra_var"] == f"limit: {ENCRYPTED_STRING}\n"


@pytest.mark.django_db
def test_retrieve_extra_var_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/extra-vars/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


NOT_OBJECT_ERROR_MSG = "Extra var is not in object format"
NOT_YAML_JSON_ERROR_MSG = "Extra var must be in JSON or YAML format"


@pytest.mark.parametrize(
    "extra_var,error_message",
    [
        ("John", NOT_OBJECT_ERROR_MSG),
        ("John, ", NOT_OBJECT_ERROR_MSG),
        ("[John, 3,]", NOT_OBJECT_ERROR_MSG),
        ('{"name": "John" - 2 }', NOT_YAML_JSON_ERROR_MSG),
    ],
)
@pytest.mark.django_db
def test_extra_var_invalid_data(client: APIClient, extra_var, error_message):
    invalid_data = {
        "extra_var": extra_var,
    }
    response = client.post(f"{api_url_v1}/extra-vars/", data=invalid_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert str(response.data["extra_var"][0]) == error_message


@pytest.mark.parametrize(
    "extra_var",
    [
        "John: Doe",
        "John: 2",
        '{"name": "John"}',
        '"age": 20',
        "---\nname: hello\nhosts: localhost\ngather_facts: false",
    ],
)
@pytest.mark.django_db
def test_extra_var_valid_data(client: APIClient, extra_var):
    valid_data = {
        "extra_var": extra_var,
    }
    response = client.post(f"{api_url_v1}/extra-vars/", data=valid_data)
    assert response.status_code == status.HTTP_201_CREATED


def assert_extra_var_data(response, expected):
    """Assert the response from ExtraVar view matches the object instance
    in DB"""
    assert response["id"] == expected.id
    assert response["extra_var"] == converted_extra_var(expected.extra_var)
    assert response["organization_id"] == expected.organization.id
