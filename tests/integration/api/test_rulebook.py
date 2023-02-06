#  Copyright 2023 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.api.conftest import api_url_v1

TEST_RULESETS_SAMPLE = """
---
- name: Test sample 001
  hosts: all
  sources:
    - ansible.eda.range:
        limit: 5
        delay: 1
      filters:
        - noop:
  rules:
    - name: r1
      condition: event.i == 1
      action:
        debug:
    - name: r2
      condition: event.i == 2
      action:
        debug:

- name: Test sample 002
  hosts: all
  sources:
    - ansible.eda.range:
        limit: 5
        delay: 1
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
    response = client.get(f"{api_url_v1}/rulebooks")
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

    response = client.post(f"{api_url_v1}/rulebooks", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED

    id_ = response.data["id"]
    assert response.data["name"] == "test-rulebook.yml"
    assert response.data["rulesets"] == TEST_RULESETS_SAMPLE
    assert response.data["project"] is None
    assert models.Rulebook.objects.filter(pk=id_).exists()

    assert len(models.Ruleset.objects.all()) == 2
    assert models.Ruleset.objects.first().name == "Test sample 001"
    assert models.Ruleset.objects.last().name == "Test sample 002"


@pytest.mark.django_db
def test_retrieve_rulebook(client: APIClient):
    obj = models.Rulebook.objects.create(
        name="test-rulebook.yml", rulesets=TEST_RULESETS_SAMPLE
    )
    response = client.get(f"{api_url_v1}/rulebooks/{obj.id}")
    assert response.status_code == status.HTTP_200_OK

    assert response.data["id"] == obj.id
    assert response.data["name"] == "test-rulebook.yml"
    assert response.data["rulesets"] == TEST_RULESETS_SAMPLE
    assert response.data["project"] is None


@pytest.mark.django_db
def test_retrieve_rulebook_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/rulebooks/42")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_retrieve_json_rulebook(client: APIClient):
    obj = models.Rulebook.objects.create(
        name="test-rulebook.yml", rulesets=TEST_RULESETS_SAMPLE
    )
    response = client.get(f"{api_url_v1}/rulebooks/{obj.id}/json")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == obj.id
    assert data["name"] == "test-rulebook.yml"
    assert len(data["rulesets"]) == 2
    assert data["rulesets"][0]["name"] == "Test sample 001"
    assert data["rulesets"][1]["name"] == "Test sample 002"


@pytest.mark.django_db
def test_retrieve_json_rulebook_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/rulebooks/42/json")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_list_rulesets_from_rulebook(client: APIClient):
    _prepare_rulesets_and_rules(client)

    response = client.get(f"{api_url_v1}/rulebooks")
    rulebook_id = response.data[0]["id"]

    response = client.get(f"{api_url_v1}/rulebooks/{rulebook_id}/rulesets")
    assert response.status_code == status.HTTP_200_OK

    assert len(response.data) == 2
    assert response.data[0]["name"] == "Test sample 001"
    assert response.data[1]["name"] == "Test sample 002"
    assert list(response.data[0]) == [
        "id",
        "name",
        "created_at",
        "modified_at",
        "source_types",
        "rule_count",
        "fired_stats",
    ]


@pytest.mark.django_db
def test_list_rulesets(client: APIClient):
    _prepare_rulesets_and_rules(client)

    response = client.get(f"{api_url_v1}/rulesets")
    assert response.status_code == status.HTTP_200_OK
    rulesets = response.data

    assert len(rulesets) == 2
    assert rulesets[0]["name"] == "Test sample 001"
    assert rulesets[0]["rule_count"] == 2
    assert rulesets[1]["name"] == "Test sample 002"
    assert rulesets[1]["rule_count"] == 1
    assert list(rulesets[0]) == [
        "id",
        "name",
        "created_at",
        "modified_at",
        "source_types",
        "rule_count",
        "fired_stats",
    ]


@pytest.mark.django_db
def test_retrieve_ruleset(client: APIClient):
    _prepare_rulesets_and_rules(client)
    response = client.get(f"{api_url_v1}/rulesets")
    rulesets = response.data

    response = client.get(f"{api_url_v1}/rulesets/{rulesets[0]['id']}")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "Test sample 001"


@pytest.mark.django_db
def test_list_rules_from_ruleset(client: APIClient):
    _prepare_rulesets_and_rules(client)
    response = client.get(f"{api_url_v1}/rulesets")
    rulesets = response.data

    response = client.get(f"{api_url_v1}/rulesets/{rulesets[0]['id']}/rules")
    assert response.status_code == status.HTTP_200_OK

    rules = response.data
    assert len(rules) == 2
    assert rules[0]["name"] == "r1"
    assert rules[1]["name"] == "r2"
    assert list(rules[0]) == [
        "id",
        "name",
        "action",
        "ruleset",
    ]


@pytest.mark.django_db
def test_retrieve_ruleset_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/rulesets/42")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_list_rules(client: APIClient):
    _prepare_rulesets_and_rules(client)

    response = client.get(f"{api_url_v1}/rules")
    assert response.status_code == status.HTTP_200_OK
    rules = response.data

    assert len(rules) == 3
    assert rules[0]["name"] == "r1"
    assert rules[1]["name"] == "r2"
    assert rules[2]["name"] == "r3"
    assert list(rules[0]) == [
        "id",
        "name",
        "action",
        "ruleset",
        "fired_stats",
    ]


@pytest.mark.django_db
def test_retrieve_rule(client: APIClient):
    _prepare_rulesets_and_rules(client)
    response = client.get(f"{api_url_v1}/rules")
    rules = response.data

    response = client.get(f"{api_url_v1}/rules/{rules[0]['id']}")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "r1"


@pytest.mark.django_db
def test_retrieve_rule_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/rules/42")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def _prepare_rulesets_and_rules(client: APIClient):
    data_in = {
        "name": "test-rulebook.yml",
        "rulesets": TEST_RULESETS_SAMPLE,
    }
    client.post(f"{api_url_v1}/rulebooks", data=data_in)
