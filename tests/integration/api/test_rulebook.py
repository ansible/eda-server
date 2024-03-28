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
import yaml
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

DUMMY_UUID = "8472ff2c-6045-4418-8d4e-46f6cffc8557"


# ------------------------------------------
# Test Rulebook:
# ------------------------------------------
@pytest.mark.django_db
def test_list_rulebooks(
    default_rulebook: models.Rulebook,
    rulebook_with_job_template: models.Rulebook,
    client: APIClient,
):
    rulebooks = [default_rulebook, rulebook_with_job_template]
    response = client.get(f"{api_url_v1}/rulebooks/")
    assert response.status_code == status.HTTP_200_OK

    for data, rulebook in zip(response.data["results"], rulebooks):
        assert_rulebook_data(data, rulebook)


@pytest.mark.django_db
def test_list_rulebooks_filter_name(
    default_rulebook: models.Rulebook,
    rulebook_with_job_template: models.Rulebook,
    client: APIClient,
):
    filter_name = default_rulebook.name
    response = client.get(f"{api_url_v1}/rulebooks/")
    response = client.get(f"{api_url_v1}/rulebooks/?name={filter_name}")
    data = response.json()["results"][0]
    assert response.status_code == status.HTTP_200_OK
    assert_rulebook_data(data, default_rulebook)


@pytest.mark.django_db
def test_list_rulebooks_filter_name_non_existant(
    default_rulebook: models.Rulebook, client: APIClient
):
    filter_name = "doesn't exist"
    response = client.get(f"{api_url_v1}/rulebooks/?name={filter_name}")
    data = response.json()["results"]
    assert response.status_code == status.HTTP_200_OK
    assert data == []


@pytest.mark.django_db
def test_list_rulebooks_filter_project(
    default_project: models.Project,
    default_rulebook: models.Rulebook,
    client: APIClient,
):
    response = client.get(
        f"{api_url_v1}/rulebooks/?project_id={default_project.id}"
    )
    data = response.json()["results"][0]
    assert response.status_code == status.HTTP_200_OK
    assert data["project_id"] == default_project.id
    assert_rulebook_data(data, default_rulebook)


@pytest.mark.django_db
def test_list_rulebooks_filter_project_non_existant(
    default_rulebook: models.Rulebook, client: APIClient
):
    filter_project = "10000"
    response = client.get(
        f"{api_url_v1}/rulebooks/?project_id={filter_project}"
    )
    data = response.json()["results"]
    assert response.status_code == status.HTTP_200_OK
    assert data == []


@pytest.mark.django_db
def test_retrieve_rulebook(
    default_rulebook: models.Rulebook, client: APIClient
):
    response = client.get(f"{api_url_v1}/rulebooks/{default_rulebook.id}/")

    assert response.status_code == status.HTTP_200_OK
    assert_rulebook_data(response.json(), default_rulebook)


@pytest.mark.django_db
def test_retrieve_rulebook_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/rulebooks/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_retrieve_json_rulebook(
    default_rulebook: models.Rulebook, client: APIClient
):
    response = client.get(
        f"{api_url_v1}/rulebooks/{default_rulebook.id}/json/"
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == default_rulebook.id
    assert data["name"] == default_rulebook.name

    rulebook_rulesets = yaml.safe_load(default_rulebook.rulesets)
    assert len(data["rulesets"]) == len(rulebook_rulesets)
    assert data["rulesets"][0]["name"] == rulebook_rulesets[0]["name"]
    assert data["rulesets"][1]["name"] == rulebook_rulesets[1]["name"]


@pytest.mark.django_db
def test_retrieve_json_rulebook_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/rulebooks/42/json/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def assert_rulebook_data(data: Dict[str, Any], rulebook: models.Rulebook):
    assert data == {
        "id": rulebook.id,
        "name": rulebook.name,
        "description": rulebook.description,
        "rulesets": rulebook.rulesets,
        "project_id": rulebook.project.id,
        "created_at": rulebook.created_at.strftime(DATETIME_FORMAT),
        "modified_at": rulebook.modified_at.strftime(DATETIME_FORMAT),
    }


# ------------------------------------------
# Test Audit Rule:
# ------------------------------------------
@pytest.mark.django_db
def test_list_audit_rules(
    audit_rule_1: models.AuditRule,
    audit_rule_2: models.AuditRule,
    client: APIClient,
):
    response = client.get(f"{api_url_v1}/audit-rules/")
    assert response.status_code == status.HTTP_200_OK
    audit_rules = response.data["results"]

    assert len(audit_rules) == 2
    assert audit_rules[0]["fired_at"] > audit_rules[1]["fired_at"]
    assert audit_rules[0]["name"] == audit_rule_2.name
    assert list(audit_rules[0]) == [
        "id",
        "name",
        "status",
        "activation_instance",
        "fired_at",
    ]


@pytest.mark.django_db
def test_list_audit_rules_filter_name(
    audit_rule_1: models.AuditRule,
    audit_rule_2: models.AuditRule,
    client: APIClient,
):
    filter_name = audit_rule_1.name
    response = client.get(f"{api_url_v1}/audit-rules/?name={filter_name}")
    assert response.status_code == status.HTTP_200_OK
    audit_rules = response.data["results"]

    assert len(audit_rules) == 1
    assert audit_rules[0]["name"] == audit_rule_1.name
    assert list(audit_rules[0]) == [
        "id",
        "name",
        "status",
        "activation_instance",
        "fired_at",
    ]


@pytest.mark.django_db
def test_list_audit_rules_filter_name_non_existent(
    audit_rule_1: models.AuditRule, client: APIClient
):
    filter_name = "doesn't exist"
    response = client.get(f"{api_url_v1}/audit-rules/?name={filter_name}")
    data = response.json()["results"]
    assert response.status_code == status.HTTP_200_OK
    assert data == []


@pytest.mark.parametrize(
    "ordering_field",
    [
        "name",
        "fired_at",
        "status",
    ],
)
@pytest.mark.django_db
def test_list_audit_rules_ordering(
    audit_rule_1: models.AuditRule,
    audit_rule_2: models.AuditRule,
    client: APIClient,
    ordering_field,
):
    response = client.get(
        f"{api_url_v1}/audit-rules/?ordering={ordering_field}"
    )
    assert response.status_code == status.HTTP_200_OK
    audit_rules = response.data["results"]
    assert len(audit_rules) == 2
    assert audit_rules[0][ordering_field] == getattr(
        audit_rule_1, ordering_field
    )

    response = client.get(
        f"{api_url_v1}/audit-rules/?ordering=-{ordering_field}"
    )
    assert response.status_code == status.HTTP_200_OK
    audit_rules = response.data["results"]
    assert len(audit_rules) == 2
    assert audit_rules[0][ordering_field] == getattr(
        audit_rule_2, ordering_field
    )


@pytest.mark.django_db
def test_list_audit_rules_ordering_activation_name(
    audit_rule_1: models.AuditRule,
    audit_rule_2: models.AuditRule,
    client: APIClient,
):
    ordering_field = "activation_instance__name"
    response = client.get(
        f"{api_url_v1}/audit-rules/?ordering={ordering_field}"
    )
    assert response.status_code == status.HTTP_200_OK
    audit_rules = response.data["results"]
    assert len(audit_rules) == 2
    assert (
        audit_rules[0]["activation_instance"]["name"]
        == audit_rule_1.activation_instance.name
    )

    response = client.get(
        f"{api_url_v1}/audit-rules/?ordering=-{ordering_field}"
    )
    assert response.status_code == status.HTTP_200_OK
    audit_rules = response.data["results"]
    assert len(audit_rules) == 2
    assert (
        audit_rules[0]["activation_instance"]["name"]
        == audit_rule_2.activation_instance.name
    )


@pytest.mark.django_db
def test_retrieve_audit_rule(
    audit_rule_1: models.AuditRule, client: APIClient
):
    response = client.get(f"{api_url_v1}/audit-rules/{audit_rule_1.id}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == audit_rule_1.name
    assert response.data["ruleset_name"] == audit_rule_1.ruleset_name


@pytest.mark.django_db
def test_retrieve_audit_rule_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/audit-rules/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_list_actions_from_audit_rule(
    audit_rule_2: models.AuditRule,
    audit_action_2: models.AuditAction,
    audit_action_3: models.AuditAction,
    client: APIClient,
):
    response = client.get(
        f"{api_url_v1}/audit-rules/{audit_rule_2.id}/actions/"
    )
    assert response.status_code == status.HTTP_200_OK

    actions = response.data["results"]
    assert len(actions) == audit_rule_2.auditaction_set.count()
    assert actions[0]["fired_at"] > actions[1]["rule_fired_at"]


@pytest.mark.django_db
def test_list_actions_from_audit_rule_filter_name(
    audit_rule_2: models.AuditRule,
    audit_action_3: models.AuditAction,
    client: APIClient,
):
    response = client.get(
        f"{api_url_v1}/audit-rules/{audit_rule_2.id}/actions/"
        f"?name={audit_action_3.name}"
    )
    assert response.status_code == status.HTTP_200_OK

    filtered_actions = response.data["results"]
    assert len(filtered_actions) == 1
    assert filtered_actions[0]["name"] == audit_action_3.name
    assert list(filtered_actions[0]) == [
        "id",
        "name",
        "status",
        "url",
        "fired_at",
        "organization_id",
        "rule_fired_at",
        "audit_rule_id",
        "status_message",
    ]


@pytest.mark.parametrize(
    "ordering_field",
    ["name", "status", "url", "fired_at"],
)
@pytest.mark.django_db
def test_list_actions_from_audit_rule_ordering(
    audit_rule_2: models.AuditRule,
    audit_action_2: models.AuditAction,
    audit_action_3: models.AuditAction,
    client: APIClient,
    ordering_field,
):
    response = client.get(
        f"{api_url_v1}/audit-rules/{audit_rule_2.id}/actions/?ordering="
        f"{ordering_field}"
    )
    assert response.status_code == status.HTTP_200_OK
    actions = response.data["results"]
    assert len(actions) == 2
    assert actions[0][ordering_field] == getattr(
        audit_action_2, ordering_field
    )

    response = client.get(
        f"{api_url_v1}/audit-rules/{audit_rule_2.id}/actions/?ordering="
        f"-{ordering_field}"
    )
    assert response.status_code == status.HTTP_200_OK
    actions = response.data["results"]
    assert len(actions) == 2
    assert actions[0][ordering_field] == getattr(
        audit_action_3, ordering_field
    )


@pytest.mark.django_db
def test_list_actions_from_audit_rule_filter_name_non_existent(
    audit_rule_2: models.AuditRule, client: APIClient
):
    filter_name = "doesn't exist"

    response = client.get(
        f"{api_url_v1}/audit-rules/{audit_rule_2.id}/actions/"
        f"?name={filter_name}"
    )
    data = response.json()["results"]
    assert response.status_code == status.HTTP_200_OK
    assert data == []


@pytest.mark.django_db
def test_list_events_from_audit_rule(
    audit_rule_2: models.AuditRule,
    audit_event_2: models.AuditEvent,
    audit_event_3: models.AuditEvent,
    client: APIClient,
):
    response = client.get(
        f"{api_url_v1}/audit-rules/{audit_rule_2.id}/events/"
    )
    assert response.status_code == status.HTTP_200_OK

    events = response.data["results"]
    assert len(events) == 2
    assert events[0]["received_at"] > events[1]["received_at"]
    assert events[0]["payload"] == events[1]["payload"]
    assert events[0]["payload"] == yaml.safe_dump(audit_event_2.payload)


@pytest.mark.parametrize(
    "ordering_field",
    ["source_name", "source_type", "received_at"],
)
@pytest.mark.django_db
def test_list_events_from_audit_rule_ordering(
    audit_rule_2: models.AuditRule,
    audit_event_2: models.AuditEvent,
    audit_event_3: models.AuditEvent,
    client: APIClient,
    ordering_field,
):
    response = client.get(
        f"{api_url_v1}/audit-rules/{audit_rule_2.id}/events/?ordering="
        f"{ordering_field}"
    )
    assert response.status_code == status.HTTP_200_OK
    events = response.data["results"]
    assert len(events) == 2
    assert events[0][ordering_field] == getattr(audit_event_2, ordering_field)

    response = client.get(
        f"{api_url_v1}/audit-rules/{audit_rule_2.id}/events/?ordering="
        f"-{ordering_field}"
    )
    assert response.status_code == status.HTTP_200_OK
    events = response.data["results"]
    assert len(events) == 2
    assert events[0][ordering_field] == getattr(audit_event_3, ordering_field)


@pytest.mark.django_db
def test_delete_project_and_rulebooks(
    default_project: models.Project,
    default_activation: models.Activation,
    default_rulebook: models.Rulebook,
    ruleset_1: models.Ruleset,
    default_rule: models.Rule,
    client: APIClient,
):
    response = client.delete(f"{api_url_v1}/projects/{default_project.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    activation = models.Activation.objects.get(pk=default_activation.id)
    assert activation.project is None
    assert activation.rulebook is None
    assert not models.Project.objects.filter(id=default_project.id).exists()
    assert not models.Rulebook.objects.filter(id=default_rulebook.id).exists()
    assert not models.Ruleset.objects.filter(id=ruleset_1.id).exists()
    assert not models.Rule.objects.filter(id=default_rule.id).exists()
