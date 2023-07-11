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

import uuid
from dataclasses import dataclass
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

DUMMY_UUID = "8472ff2c-6045-4418-8d4e-46f6cffc8557"


@dataclass
class InitData:
    activation: models.Activation
    project: models.Project
    project_1: models.Project
    rulebook: models.Rulebook
    rulebook_1: models.Rulebook
    ruleset: models.Ruleset
    ruleset_1: models.Ruleset
    ruleset_2: models.Ruleset
    rule: models.Rule
    audit_rule: models.AuditRule
    audit_action: models.AuditAction
    audit_event: models.AuditEvent


# ------------------------------------------
# Test Rulebook:
# ------------------------------------------
@pytest.mark.django_db
def test_list_rulebooks(client: APIClient, init_db):
    rulebooks = [init_db.rulebook, init_db.rulebook_1]
    response = client.get(f"{api_url_v1}/rulebooks/")
    assert response.status_code == status.HTTP_200_OK

    for data, rulebook in zip(response.data["results"], rulebooks):
        assert_rulebook_data(data, rulebook)


@pytest.mark.django_db
def test_list_rulebooks_filter_name(client: APIClient, init_db):
    filter_name = "another"
    response = client.get(f"{api_url_v1}/rulebooks/?name={filter_name}")
    data = response.json()["results"][0]
    rulebook = init_db.rulebook_1
    assert response.status_code == status.HTTP_200_OK
    assert_rulebook_data(data, rulebook)


@pytest.mark.django_db
def test_list_rulebooks_filter_name_non_existant(client: APIClient, init_db):
    filter_name = "doesn't exist"
    response = client.get(f"{api_url_v1}/rulebooks/?name={filter_name}")
    data = response.json()["results"]
    assert response.status_code == status.HTTP_200_OK
    assert data == []


@pytest.mark.django_db
def test_list_rulebooks_filter_project(client: APIClient, init_db):
    filter_project = init_db.project.id
    rulebook = init_db.rulebook
    response = client.get(
        f"{api_url_v1}/rulebooks/?project_id={filter_project}"
    )
    data = response.json()["results"][0]
    assert response.status_code == status.HTTP_200_OK
    assert data["project_id"] == filter_project
    assert_rulebook_data(data, rulebook)


@pytest.mark.django_db
def test_list_rulebooks_filter_project_non_existant(client: APIClient):
    filter_project = "10000"
    response = client.get(
        f"{api_url_v1}/rulebooks/?project_id={filter_project}"
    )
    data = response.json()["results"]
    assert response.status_code == status.HTTP_200_OK
    assert data == []


@pytest.mark.django_db
def test_retrieve_rulebook(client: APIClient, init_db):
    rulebook = init_db.rulebook
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
        name="test-rulebook.yml",
        rulesets=TEST_RULESETS_SAMPLE,
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
def test_list_rulesets_from_rulebook(client: APIClient, init_db):
    rulebook_id = init_db.rulebook.id

    response = client.get(f"{api_url_v1}/rulebooks/{rulebook_id}/rulesets/")
    assert response.status_code == status.HTTP_200_OK
    response_rulesets = response.data["results"]

    assert len(response_rulesets) == 2
    assert response_rulesets[0]["name"] == "test-ruleset"
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
        "project_id": rulebook.project.id,
        "created_at": rulebook.created_at.strftime(DATETIME_FORMAT),
        "modified_at": rulebook.modified_at.strftime(DATETIME_FORMAT),
    }


# ------------------------------------------
# Test Ruleset:
# ------------------------------------------
@pytest.mark.django_db
def test_list_rulesets(client: APIClient, init_db):
    response = client.get(f"{api_url_v1}/rulesets/")
    assert response.status_code == status.HTTP_200_OK
    rulesets = response.data["results"]

    assert len(rulesets) == 3
    assert rulesets[0]["name"] == "test-ruleset"
    assert rulesets[0]["rule_count"] == 1
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
def test_rulesets_filter_name(client: APIClient, init_db):
    test_ruleset = init_db.ruleset_2
    filter_name = "filter"
    response = client.get(f"{api_url_v1}/rulesets/?name={filter_name}")
    assert response.status_code == status.HTTP_200_OK
    ruleset = response.json()["results"]

    assert len(ruleset) == 1
    assert ruleset[0] == {
        "id": test_ruleset.id,
        "name": test_ruleset.name,
        "created_at": test_ruleset.created_at.strftime(DATETIME_FORMAT),
        "modified_at": test_ruleset.modified_at.strftime(DATETIME_FORMAT),
        "source_types": ["range"],
        "rule_count": 0,
        "fired_stats": [{}],
    }


@pytest.mark.django_db
def test_rulesets_filter_name_none_exist(client: APIClient, init_db):
    filter_name = "not in existance"
    response = client.get(f"{api_url_v1}/rulesets/?name={filter_name}")
    assert response.status_code == status.HTTP_200_OK
    rulesets = response.data["results"]
    assert rulesets == []


@pytest.mark.django_db
def test_retrieve_ruleset(client: APIClient, init_db):
    ruleset_id = init_db.ruleset.id
    response = client.get(f"{api_url_v1}/rulesets/{ruleset_id}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "test-ruleset"


@pytest.mark.django_db
def test_list_rules_from_ruleset(client: APIClient, init_db):
    ruleset_id = init_db.ruleset.id

    response = client.get(f"{api_url_v1}/rulesets/{ruleset_id}/rules/")
    assert response.status_code == status.HTTP_200_OK

    rules = response.data["results"]
    assert len(rules) == 1
    assert rules[0]["name"] == "say hello"
    assert list(rules[0]) == [
        "id",
        "name",
        "action",
        "ruleset_id",
    ]


@pytest.mark.django_db
def test_retrieve_ruleset_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/rulesets/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ------------------------------------------
# Test Rule:
# ------------------------------------------
@pytest.mark.django_db
def test_list_rules(client: APIClient, init_db):
    response = client.get(f"{api_url_v1}/rules/")
    assert response.status_code == status.HTTP_200_OK
    rules = response.data["results"]

    assert len(rules) == 1
    assert rules[0]["name"] == "say hello"
    assert list(rules[0]) == [
        "id",
        "name",
        "action",
        "ruleset_id",
        "fired_stats",
        "rulebook_id",
        "project_id",
    ]


@pytest.mark.django_db
def test_retrieve_rule(client: APIClient, init_db):
    rule_id = init_db.rule.id

    response = client.get(f"{api_url_v1}/rules/{rule_id}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "say hello"


@pytest.mark.django_db
def test_retrieve_rule_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/rules/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ------------------------------------------
# Test Audit Rule:
# ------------------------------------------
@pytest.mark.django_db
def test_list_audit_rules(client: APIClient, init_db):
    response = client.get(f"{api_url_v1}/audit-rules/")
    assert response.status_code == status.HTTP_200_OK
    audit_rules = response.data["results"]

    assert len(audit_rules) == 2
    assert audit_rules[0]["fired_at"] > audit_rules[1]["fired_at"]
    assert audit_rules[0]["name"] == "test_action"
    assert list(audit_rules[0]) == [
        "id",
        "name",
        "status",
        "activation_instance",
        "fired_at",
    ]


@pytest.mark.django_db
def test_list_audit_rules_filter_name(client: APIClient, init_db):
    filter_name = "test_action"
    response = client.get(f"{api_url_v1}/audit-rules/?name={filter_name}")
    assert response.status_code == status.HTTP_200_OK
    audit_rules = response.data["results"]

    assert len(audit_rules) == 2
    assert audit_rules[0]["name"] == "test_action"
    assert list(audit_rules[0]) == [
        "id",
        "name",
        "status",
        "activation_instance",
        "fired_at",
    ]


@pytest.mark.django_db
def test_list_aduit_rules_filter_name_non_existant(client: APIClient, init_db):
    filter_name = "doesn't exist"
    response = client.get(f"{api_url_v1}/audit-rules/?name={filter_name}")
    data = response.json()["results"]
    assert response.status_code == status.HTTP_200_OK
    assert data == []


@pytest.mark.django_db
def test_retrieve_audit_rule(client: APIClient, init_db):
    audit_rule_id = init_db.audit_rule.id

    response = client.get(f"{api_url_v1}/audit-rules/{audit_rule_id}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "test_action"
    assert response.data["ruleset_name"] == "test-audit-ruleset-name"


@pytest.mark.django_db
def test_retrieve_audit_rule_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/audit-rules/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_list_actions_from_audit_rule(client: APIClient, init_db):
    audit_rule_id = init_db.audit_rule.id

    response = client.get(f"{api_url_v1}/audit-rules/{audit_rule_id}/actions/")
    assert response.status_code == status.HTTP_200_OK

    actions = response.data["results"]
    assert len(actions) == 2
    assert actions[0]["fired_at"] > actions[1]["rule_fired_at"]


@pytest.mark.django_db
def test_list_actions_from_audit_rule_filter_name(client: APIClient, init_db):
    filter_name = "action-1"
    audit_rule_id = init_db.audit_rule.id

    response = client.get(
        f"{api_url_v1}/audit-rules/{audit_rule_id}/actions/?name={filter_name}"
    )
    assert response.status_code == status.HTTP_200_OK

    filtered_actions = response.data["results"]
    assert len(filtered_actions) == 1
    assert filtered_actions[0]["name"] == "action-1"
    assert list(filtered_actions[0]) == [
        "id",
        "name",
        "status",
        "url",
        "fired_at",
        "rule_fired_at",
        "audit_rule_id",
    ]


@pytest.mark.django_db
def test_list_actions_from_audit_rule_filter_name_non_existant(
    client: APIClient, init_db
):
    filter_name = "doesn't exist"
    audit_rule_id = init_db.audit_rule.id

    response = client.get(
        f"{api_url_v1}/audit-rules/{audit_rule_id}/actions/?name={filter_name}"
    )
    data = response.json()["results"]
    assert response.status_code == status.HTTP_200_OK
    assert data == []


@pytest.mark.django_db
def test_list_events_from_audit_rule(client: APIClient, init_db):
    audit_rule_id = init_db.audit_rule.id

    response = client.get(f"{api_url_v1}/audit-rules/{audit_rule_id}/events/")
    assert response.status_code == status.HTTP_200_OK

    events = response.data["results"]
    assert len(events) == 4


# ------------------------------------------
# Test Audit Event:
# ------------------------------------------
@pytest.mark.django_db
def test_list_audit_events(client: APIClient, init_db):
    response = client.get(f"{api_url_v1}/audit-events/")
    assert response.status_code == status.HTTP_200_OK
    audit_events = response.data["results"]

    assert len(audit_events) == 4
    assert audit_events[0]["rule_fired_at"] > audit_events[1]["rule_fired_at"]


@pytest.mark.django_db
def test_list_audit_events_filter_name(client: APIClient, init_db):
    filter_name = "event-1"

    response = client.get(
        f"{api_url_v1}/audit-events/?source_name={filter_name}"
    )
    assert response.status_code == status.HTTP_200_OK
    filtered_audit_events = response.data["results"]

    assert len(filtered_audit_events) == 1
    assert filtered_audit_events[0]["source_name"] == "event-1"
    assert list(filtered_audit_events[0]) == [
        "id",
        "source_name",
        "source_type",
        "received_at",
        "payload",
        "rule_fired_at",
        "audit_actions",
    ]


@pytest.mark.django_db
def test_list_audit_events_filter_name_non_existant(
    client: APIClient, init_db
):
    filter_name = "doesn't exist"

    response = client.get(
        f"{api_url_v1}/audit-events/?source_name={filter_name}"
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["results"]
    assert data == []


@pytest.mark.django_db
def test_retrieve_audit_event(client: APIClient, init_db):
    audit_event_id = init_db.audit_event.id

    response = client.get(f"{api_url_v1}/audit-events/{audit_event_id}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["source_name"] == "event-1"


@pytest.mark.django_db
def test_retrieve_audit_event_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/audit-events/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_delete_project_and_rulebooks(client: APIClient, init_db):
    project_id = init_db.project.id
    response = client.delete(f"{api_url_v1}/projects/{project_id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    activation = models.Activation.objects.get(pk=init_db.activation.id)
    assert activation.project is None
    assert activation.rulebook is None
    assert not models.Project.objects.filter(id=project_id).exists()
    assert not models.Rulebook.objects.filter(id=init_db.rulebook.id).exists()
    assert not models.Ruleset.objects.filter(id=init_db.ruleset.id).exists()
    assert not models.Rule.objects.filter(id=init_db.rule.id).exists()


@pytest.fixture
def init_db():
    project = models.Project.objects.create(
        name="test-project",
        description="Test Project",
        url="https://github.com/eda-project",
        import_state=models.Project.ImportState.COMPLETED,
    )

    project_1 = models.Project.objects.create(
        name="test-project-1",
        description="Test Project 1",
        url="https://git.example.com/acme/project-01",
        import_state=models.Project.ImportState.COMPLETED,
    )

    rulebook = models.Rulebook.objects.create(
        name="test-rulebook.yml",
        rulesets=TEST_RULESETS_SAMPLE,
        project=project,
    )

    rulebook_1 = models.Rulebook.objects.create(
        name="test-another-rulebook.yml",
        rulesets=TEST_RULESETS_SAMPLE,
        project=project_1,
    )

    source_list = [
        {
            "name": "<unnamed>",
            "type": "range",
            "config": {"limit": 5},
            "source": "ansible.eda.range",
        }
    ]

    ruleset = models.Ruleset.objects.create(
        name="test-ruleset",
        sources=source_list,
        rulebook=rulebook,
    )

    ruleset_1 = models.Ruleset.objects.create(
        name="test-ruleset-01",
        sources=source_list,
        rulebook=rulebook,
    )

    ruleset_2 = models.Ruleset.objects.create(
        name="filter-test-ruleset",
        sources=source_list,
        rulebook=rulebook_1,
    )

    rule = models.Rule.objects.create(
        name="say hello",
        action={"run_playbook": {"name": "ansible.eda.hello"}},
        ruleset=ruleset,
    )
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    activation = models.Activation.objects.create(
        name="test-activation",
        rulebook=rulebook,
        project=project,
        user=user,
    )
    activation_instance = models.ActivationInstance.objects.create(
        activation=activation,
    )
    audit_rule = models.AuditRule.objects.create(
        name="test_action",
        fired_at="2023-03-23T01:36:36.835248Z",
        rule_uuid=DUMMY_UUID,
        ruleset_uuid=DUMMY_UUID,
        ruleset_name="test-audit-ruleset-name",
        activation_instance=activation_instance,
    )
    models.AuditRule.objects.create(
        name="test_action",
        fired_at="2023-03-23T01:46:36.835248Z",
        rule_uuid=DUMMY_UUID,
        ruleset_uuid=DUMMY_UUID,
        ruleset_name="test-audit-ruleset-name",
        activation_instance=activation_instance,
    )

    action_1 = models.AuditAction.objects.create(
        id=str(uuid.uuid4()),
        name="action-1",
        audit_rule=audit_rule,
        status="pending",
        rule_fired_at="2023-03-23T01:36:36.835248Z",
        fired_at="2023-03-30T20:59:42.042148Z",
    )
    action_2 = models.AuditAction.objects.create(
        id=str(uuid.uuid4()),
        name="action-2",
        audit_rule=audit_rule,
        status="pending",
        rule_fired_at="2023-03-23T01:36:36.835248Z",
        fired_at="2023-03-30T20:59:42.052148Z",
    )
    audit_event_1 = models.AuditEvent.objects.create(
        id=str(uuid.uuid4()),
        source_name="event-1",
        source_type="type-1",
        rule_fired_at="2023-03-23T01:37:36.835248Z",
        received_at="2023-03-30T20:59:42.042148Z",
    )
    audit_event_2 = models.AuditEvent.objects.create(
        id=str(uuid.uuid4()),
        source_name="event-2",
        source_type="type-2",
        rule_fired_at="2023-03-23T01:36:36.835248Z",
        received_at="2023-03-30T20:59:42.042148Z",
    )
    audit_event_3 = models.AuditEvent.objects.create(
        id=str(uuid.uuid4()),
        source_name="event-3",
        source_type="type-3",
        rule_fired_at="2023-03-23T03:58:36.835248Z",
        received_at="2023-03-30T20:59:42.042148Z",
    )
    audit_event_4 = models.AuditEvent.objects.create(
        id=str(uuid.uuid4()),
        source_name="event-2",
        source_type="type-2",
        rule_fired_at="2023-03-23T06:56:36.835248Z",
        received_at="2023-03-30T20:59:42.042148Z",
    )
    audit_event_1.audit_actions.add(action_1)
    audit_event_1.audit_actions.add(action_2)
    audit_event_2.audit_actions.add(action_1)
    audit_event_3.audit_actions.add(action_2)
    audit_event_4.audit_actions.add(action_2)

    return InitData(
        activation=activation,
        project=project,
        project_1=project,
        rulebook=rulebook,
        rulebook_1=rulebook_1,
        ruleset=ruleset,
        ruleset_1=ruleset_1,
        ruleset_2=ruleset_2,
        rule=rule,
        audit_rule=audit_rule,
        audit_action=action_1,
        audit_event=audit_event_1,
    )
