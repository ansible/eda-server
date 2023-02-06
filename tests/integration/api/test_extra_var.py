import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.api.conftest import api_url_v1

TEST_EXTRA_VAR = """
---
collections:
- community.general
- aap.eda  # 1.0.0
""".strip()


@pytest.mark.django_db
def test_list_extra_var(client: APIClient):
    obj = models.ExtraVar.objects.create(
        name="test-extra-var.yml", extra_var=TEST_EXTRA_VAR
    )
    response = client.get(f"{api_url_v1}/extra-vars")
    assert response.status_code == status.HTTP_200_OK
    assert response.data == [
        {
            "id": obj.id,
            "project": None,
            "name": "test-extra-var.yml",
            "extra_var": TEST_EXTRA_VAR,
        }
    ]


@pytest.mark.django_db
def test_create_extra_var(client: APIClient):
    data_in = {
        "name": "test-extra-var.yml",
        "extra_var": TEST_EXTRA_VAR,
    }
    response = client.post(f"{api_url_v1}/extra-vars", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    id_ = response.data["id"]
    assert response.data == {
        "id": id_,
        "project": None,
        "name": "test-extra-var.yml",
        "extra_var": TEST_EXTRA_VAR,
    }
    assert models.ExtraVar.objects.filter(pk=id_).exists()


@pytest.mark.django_db
def test_retrieve_extra_var(client: APIClient):
    obj = models.ExtraVar.objects.create(
        name="test-extra-var.yml", extra_var=TEST_EXTRA_VAR
    )
    response = client.get(f"{api_url_v1}/extra-vars/{obj.id}")
    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        "id": obj.id,
        "project": None,
        "name": "test-extra-var.yml",
        "extra_var": TEST_EXTRA_VAR,
    }


@pytest.mark.django_db
def test_retrieve_extra_var_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/extra-vars/42")
    assert response.status_code == status.HTTP_404_NOT_FOUND
