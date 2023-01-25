import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models

TEST_RULESETS_SAMPLE = """
---
- name: Test simple 001
  hosts: all
  sources:
    - name: range
      range:
        limit: 5
  rules:
    - name: r1
      condition: event.i == 1
      action:
        debug:
    - name: r2
      condition: event.i == 2
      action:
        debug:

- name: Test simple 002
  hosts: all
  sources:
    - name: range
      range:
        limit: 5
  rules:
    - name: r3
      condition: event.i == 2
      action:
        debug:
""".strip()


@pytest.mark.django_db
def test_list_rulebooks(client: APIClient):
    obj = models.Rulebook.objects.create(
        name="test-rulebook.yml", rulesets=TEST_RULESETS_SAMPLE
    )
    response = client.get("/eda/api/v1/rulebooks")
    assert response.status_code == status.HTTP_200_OK
    rulebook = response.data[0]

    assert rulebook["id"] == obj.id
    assert rulebook["name"] == "test-rulebook.yml"
    assert rulebook["rulesets"] == TEST_RULESETS_SAMPLE
    assert rulebook["project"] is None


@pytest.mark.django_db
def test_create_rulebook(client: APIClient):
    data_in = {
        "name": "test-rulebook.yml",
        "rulesets": TEST_RULESETS_SAMPLE,
    }

    response = client.post("/eda/api/v1/rulebooks", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED

    id_ = response.data["id"]
    assert response.data["name"] == "test-rulebook.yml"
    assert response.data["rulesets"] == TEST_RULESETS_SAMPLE
    assert response.data["project"] is None
    assert models.Rulebook.objects.filter(pk=id_).exists()

    assert len(models.Ruleset.objects.all()) == 2
    assert models.Ruleset.objects.first().name == "Test simple 001"
    assert models.Ruleset.objects.last().name == "Test simple 002"


@pytest.mark.django_db
def test_retrieve_rulebook(client: APIClient):
    obj = models.Rulebook.objects.create(
        name="test-rulebook.yml", rulesets=TEST_RULESETS_SAMPLE
    )
    response = client.get(f"/eda/api/v1/rulebooks/{obj.id}")
    assert response.status_code == status.HTTP_200_OK

    assert response.data["id"] == obj.id
    assert response.data["name"] == "test-rulebook.yml"
    assert response.data["rulesets"] == TEST_RULESETS_SAMPLE
    assert response.data["project"] is None


@pytest.mark.django_db
def test_retrieve_rulebook_not_exist(client: APIClient):
    response = client.get("/eda/api/v1/rulebooks/42")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_retrieve_json_rulebook(client: APIClient):
    obj = models.Rulebook.objects.create(
        name="test-rulebook.yml", rulesets=TEST_RULESETS_SAMPLE
    )
    response = client.get(f"/eda/api/v1/rulebooks/{obj.id}/json")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == obj.id
    assert data["name"] == "test-rulebook.yml"
    assert len(data["rulesets"]) == 2
    assert data["rulesets"][0]["name"] == "Test simple 001"
    assert data["rulesets"][1]["name"] == "Test simple 002"


@pytest.mark.django_db
def test_retrieve_json_rulebook_not_exist(client: APIClient):
    response = client.get("/eda/api/v1/rulebooks/42/json")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_list_rulesets_from_rulebook(client: APIClient):
    data_in = {
        "name": "test-rulebook.yml",
        "rulesets": TEST_RULESETS_SAMPLE,
    }
    response = client.post("/eda/api/v1/rulebooks", data=data_in)

    response = client.get("/eda/api/v1/rulebooks")
    rulebook_id = response.data[0]["id"]

    response = client.get(f"/eda/api/v1/rulebooks/{rulebook_id}/rulesets")
    assert response.status_code == status.HTTP_200_OK

    assert len(response.data) == 2
    assert response.data[0]["name"] == "Test simple 001"
    assert response.data[1]["name"] == "Test simple 002"
    assert list(response.data[0]) == [
        "id",
        "name",
        "source_types",
        "rule_count",
        "fired_stats",
    ]
