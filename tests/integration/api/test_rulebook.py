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

from typing import Any, Dict

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.constants import api_url_v1

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

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


# ------------------------------------------
# Test Rulebook:
# ------------------------------------------
@pytest.mark.django_db
def test_list_rulebooks(client: APIClient):
    rulebooks = models.Rulebook.objects.bulk_create(
        [
            models.Rulebook(
                name="test-rulebook-00.yml", rulesets=TEST_RULESETS_SAMPLE
            ),
            models.Rulebook(
                name="test-rulebook-01.yml", rulesets=TEST_RULESETS_SAMPLE
            ),
        ]
    )
    response = client.get(f"{api_url_v1}/rulebooks/")
    assert response.status_code == status.HTTP_200_OK

    for data, rulebook in zip(response.data["results"], rulebooks):
        assert_rulebook_data(data, rulebook)


@pytest.mark.django_db
def test_list_rulebooks_filter_name(client: APIClient):
    rulebooks = models.Rulebook.objects.bulk_create(
        [
            models.Rulebook(
                name="test-rulebook-00.yml", rulesets=TEST_RULESETS_SAMPLE
            ),
            models.Rulebook(
                name="test-rulebook-01.yml", rulesets=TEST_RULESETS_SAMPLE
            ),
        ]
    )

    filter_name = "00"
    response = client.get(f"{api_url_v1}/rulebooks/?name={filter_name}")
    data = response.json()["results"][0]
    rulebook = rulebooks[0]
    assert response.status_code == status.HTTP_200_OK
    assert_rulebook_data(data, rulebook)


@pytest.mark.django_db
def test_list_rulebooks_filter_name_non_existant(client: APIClient):
    models.Rulebook.objects.bulk_create(
        [
            models.Rulebook(
                name="test-rulebook-00.yml", rulesets=TEST_RULESETS_SAMPLE
            ),
            models.Rulebook(
                name="test-rulebook-01.yml", rulesets=TEST_RULESETS_SAMPLE
            ),
        ]
    )

    filter_name = "doesn't exist"
    response = client.get(f"{api_url_v1}/rulebooks/?name={filter_name}")
    data = response.json()["results"]
    assert response.status_code == status.HTTP_200_OK
    assert data == []


@pytest.mark.django_db
def test_create_rulebook(client: APIClient):
    data_in = {
        "name": "test-rulebook.yml",
        "rulesets": TEST_RULESETS_SAMPLE,
    }

    response = client.post(f"{api_url_v1}/rulebooks/", data=data_in)
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
    rulebook = models.Rulebook.objects.create(
        name="test-rulebook.yml", rulesets=TEST_RULESETS_SAMPLE
    )
    response = client.get(f"{api_url_v1}/rulebooks/{rulebook.id}/")

    assert response.status_code == status.HTTP_200_OK
    assert_rulebook_data(response.json(), rulebook)


@pytest.mark.django_db
def test_retrieve_rulebook_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/rulebooks/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_retrieve_json_rulebook(client: APIClient):
    obj = models.Rulebook.objects.create(
        name="test-rulebook.yml", rulesets=TEST_RULESETS_SAMPLE
    )
    response = client.get(f"{api_url_v1}/rulebooks/{obj.id}/json/")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == obj.id
    assert data["name"] == "test-rulebook.yml"
    assert len(data["rulesets"]) == 2
    assert data["rulesets"][0]["name"] == "Test sample 001"
    assert data["rulesets"][1]["name"] == "Test sample 002"


@pytest.mark.django_db
def test_retrieve_json_rulebook_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/rulebooks/42/json/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_list_rulesets_from_rulebook(client: APIClient):
    _prepare_rulesets_and_rules(client)

    response = client.get(f"{api_url_v1}/rulebooks/")
    rulebook_id = response.data["results"][0]["id"]

    response = client.get(f"{api_url_v1}/rulebooks/{rulebook_id}/rulesets/")
    assert response.status_code == status.HTTP_200_OK
    response_rulesets = response.data["results"]

    assert len(response_rulesets) == 2
    assert response_rulesets[0]["name"] == "Test sample 001"
    assert response_rulesets[1]["name"] == "Test sample 002"
    assert list(response_rulesets[0]) == [
        "id",
        "name",
        "created_at",
        "modified_at",
        "source_types",
        "rule_count",
        "fired_stats",
    ]


def assert_rulebook_data(data: Dict[str, Any], rulebook: models.Rulebook):
    assert data == {
        "id": rulebook.id,
        "name": rulebook.name,
        "description": rulebook.description,
        "rulesets": rulebook.rulesets,
        "project": rulebook.project,
        "created_at": rulebook.created_at.strftime(DATETIME_FORMAT),
        "modified_at": rulebook.modified_at.strftime(DATETIME_FORMAT),
    }


# ------------------------------------------
# Test Ruleset:
# ------------------------------------------
@pytest.mark.django_db
def test_list_rulesets(client: APIClient):
    _prepare_rulesets_and_rules(client)

    response = client.get(f"{api_url_v1}/rulesets/")
    assert response.status_code == status.HTTP_200_OK
    rulesets = response.data["results"]

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
    # TODO: Refactor to not call list when testing retrieve
    response = client.get(f"{api_url_v1}/rulesets/")
    rulesets = response.data

    ruleset_id = rulesets["results"][0]["id"]
    response = client.get(f"{api_url_v1}/rulesets/{ruleset_id}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "Test sample 001"


@pytest.mark.django_db
def test_list_rules_from_ruleset(client: APIClient):
    _prepare_rulesets_and_rules(client)
    # TODO: Refactor to not call list when testing retrieve
    response = client.get(f"{api_url_v1}/rulesets/")
    rulesets = response.data

    ruleset_id = rulesets["results"][0]["id"]
    response = client.get(f"{api_url_v1}/rulesets/{ruleset_id}/rules/")
    assert response.status_code == status.HTTP_200_OK

    rules = response.data["results"]
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
    response = client.get(f"{api_url_v1}/rulesets/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ------------------------------------------
# Test Rule:
# ------------------------------------------
@pytest.mark.django_db
def test_list_rules(client: APIClient):
    _prepare_rulesets_and_rules(client)

    response = client.get(f"{api_url_v1}/rules/")
    assert response.status_code == status.HTTP_200_OK
    rules = response.data["results"]

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
    # TODO: Refactor to not call list when testing retrieve
    response = client.get(f"{api_url_v1}/rules/")
    rules = response.data

    rule_id = rules["results"][0]["id"]
    response = client.get(f"{api_url_v1}/rules/{rule_id}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "r1"


@pytest.mark.django_db
def test_retrieve_rule_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/rules/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def _prepare_rulesets_and_rules(client: APIClient):
    # TODO: Refactor to not use API to populate database with initial data
    data_in = {
        "name": "test-rulebook.yml",
        "rulesets": TEST_RULESETS_SAMPLE,
    }
    client.post(f"{api_url_v1}/rulebooks/", data=data_in)
