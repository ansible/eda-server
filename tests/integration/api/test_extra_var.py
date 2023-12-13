import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.constants import api_url_v1

TEST_EXTRA_VAR = """
---
collections:
- community.general
- aap.eda  # 1.0.0
""".strip()


@pytest.mark.django_db
def test_list_extra_var(client: APIClient):
    obj = models.ExtraVar.objects.create(extra_var=TEST_EXTRA_VAR)
    response = client.get(f"{api_url_v1}/extra-vars/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["results"] == [
        {
            "id": obj.id,
            "extra_var": TEST_EXTRA_VAR,
        }
    ]


@pytest.mark.django_db
def test_create_extra_var(client: APIClient):
    data_in = {
        "extra_var": TEST_EXTRA_VAR,
    }
    response = client.post(f"{api_url_v1}/extra-vars/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    id_ = response.data["id"]
    assert response.data == {
        "id": id_,
        "extra_var": TEST_EXTRA_VAR,
    }
    assert models.ExtraVar.objects.filter(pk=id_).exists()


@pytest.mark.django_db
def test_retrieve_extra_var(client: APIClient):
    obj = models.ExtraVar.objects.create(extra_var=TEST_EXTRA_VAR)
    response = client.get(f"{api_url_v1}/extra-vars/{obj.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        "id": obj.id,
        "extra_var": TEST_EXTRA_VAR,
    }


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
