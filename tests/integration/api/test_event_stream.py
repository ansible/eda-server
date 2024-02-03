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
from unittest import mock

import pytest
import yaml
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from aap_eda.core.enums import Action, ResourceType
from tests.integration.constants import api_url_v1

TEST_RULESETS = """
---
- name: PG Notify Template Event Stream
  hosts: all
  sources:
    - name: my_range
      ansible.eda.range:
        limit: 5
      complementary_source:
        type: ansible.eda.pg_listener
        name: Postgres Listener
        args:
          dsn: "{{ EDA_PG_NOTIFY_DSN }}"
          channels:
            - "{{ EDA_PG_NOTIFY_CHANNEL }}"
      extra_vars:
        EDA_PG_NOTIFY_DSN: "{{ settings.PG_NOTIFY_DSN }}"
        EDA_PG_NOTIFY_CHANNEL: "{{ event_stream.channel_name }}"
      encrypt_vars:
        - EDA_PG_NOTIFY_DSN
  rules:
    - name: Post event
      condition: true
      action:
        pg_notify:
          dsn: "{{ EDA_PG_NOTIFY_DSN }}"
          channel: "{{ EDA_PG_NOTIFY_CHANNEL }}"
          event: "{{ event }}"
"""


@pytest.mark.django_db
def test_list_event_streams(
    client: APIClient,
    check_permission_mock: mock.Mock,
    default_de: models.DecisionEnvironment,
    default_user: models.User,
):
    event_streams = models.EventStream.objects.bulk_create(
        [
            models.EventStream(
                uuid=uuid.uuid4(),
                name="test-event_stream-1",
                source_type="ansible.eda.range",
                args='{"limit": 5, "delay": 1}',
                user=default_user,
                decision_environment_id=default_de.id,
            ),
            models.EventStream(
                uuid=uuid.uuid4(),
                name="test-event_stream-2",
                source_type="ansible.eda.range",
                args={"limit": 6, "delay": 2},
                user=default_user,
                decision_environment_id=default_de.id,
            ),
        ]
    )

    response = client.get(f"{api_url_v1}/event-streams/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 2
    assert response.data["results"][1]["uuid"] == str(event_streams[0].uuid)
    assert (
        response.data["results"][1]["source_type"]
        == event_streams[0].source_type
    )
    assert response.data["results"][1]["name"] == event_streams[0].name
    assert response.data["results"][1]["user"] == "luke.skywalker"

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.EVENT_STREAAM, Action.READ
    )


@pytest.mark.django_db
def test_retrieve_event_stream(
    client: APIClient,
    check_permission_mock: mock.Mock,
    default_de: models.DecisionEnvironment,
    default_user: models.User,
):
    event_stream = models.EventStream.objects.create(
        uuid=uuid.uuid4(),
        name="test-event_stream-1",
        source_type="ansible.eda.range",
        args={"limit": 5, "delay": 1},
        user=default_user,
        decision_environment_id=default_de.id,
    )

    response = client.get(f"{api_url_v1}/event-streams/{event_stream.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == event_stream.name
    assert response.data["source_type"] == event_stream.source_type
    assert response.data["user"] == "luke.skywalker"

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.EVENT_STREAM, Action.READ
    )


@pytest.mark.django_db
def test_create_event_stream(
    client: APIClient,
    check_permission_mock: mock.Mock,
    default_de: models.DecisionEnvironment,
):
    models.Rulebook.objects.create(
        name=settings.PG_NOTIFY_TEMPLATE_RULEBOOK,
        rulesets=TEST_RULESETS,
    )

    data_in = {
        "name": "test_event_stream",
        "source_type": "ansible.eda.generic",
        "args": '{"limit": 1, "delay": 5}',
        "decision_environment_id": default_de.id,
    }
    response = client.post(f"{api_url_v1}/event-streams/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    result = response.data
    assert result["name"] == "test_event_stream"
    assert result["source_type"] == "ansible.eda.generic"
    assert result["args"] == yaml.safe_dump("delay: 5\nlimit: 1\n")
    assert result["user"] == "test.admin"

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.SOURCE, Action.CREATE
    )


@pytest.mark.django_db
def test_create_event_stream_bad_args(
    client: APIClient,
    check_permission_mock: mock.Mock,
    default_de: models.DecisionEnvironment,
):
    data_in = {
        "name": "test_event_stream",
        "type": "ansible.eda.generic",
        "args": "gobbledegook",
        "decision_environment_id": default_de.id,
    }
    response = client.post(f"{api_url_v1}/event-streams/", data=data_in)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    result = response.data
    assert (
        str(result["args"][0])
        == "The 'args' field must be a YAML object (dictionary)"
    )

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.SOURCE, Action.CREATE
    )


@pytest.mark.django_db
def test_create_event_stream_empty_args(
    client: APIClient,
    check_permission_mock: mock.Mock,
    default_de: models.DecisionEnvironment,
):
    data_in = {
        "name": "test_event_stream",
        "type": "ansible.eda.generic",
        "decision_environment_id": default_de.id,
    }
    response = client.post(f"{api_url_v1}/event-streams/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.SOURCE, Action.CREATE
    )


@pytest.mark.django_db
def test_create_event_stream_bad_de(
    client: APIClient,
    check_permission_mock: mock.Mock,
):
    data_in = {
        "name": "test_event_stream",
        "type": "ansible.eda.generic",
        "decision_environment_id": 99999,
    }
    response = client.post(f"{api_url_v1}/event-streams/", data=data_in)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    result = response.data
    assert (
        str(result["decision_environment_id"][0])
        == "DecisionEnvironment with id 99999 does not exist"
    )
    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.SOURCE, Action.CREATE
    )


@pytest.mark.django_db
def test_create_event_stream_no_de(
    client: APIClient,
    check_permission_mock: mock.Mock,
):
    data_in = {
        "name": "test_event_stream",
        "type": "ansible.eda.generic",
    }
    response = client.post(f"{api_url_v1}/event-streams/", data=data_in)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    result = response.data
    assert (
        str(result["decision_environment_id"][0]) == "This field is required."
    )
    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.SOURCE, Action.CREATE
    )
