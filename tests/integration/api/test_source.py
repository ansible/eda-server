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
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from aap_eda.core.enums import Action, ResourceType
from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_list_sources(client: APIClient, check_permission_mock: mock.Mock):
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    sources = models.Source.objects.bulk_create(
        [
            models.Source(
                uuid=uuid.uuid4(),
                name="test-source-1",
                type="ansible.eda.range",
                args={"limit": 5, "delay": 1},
                user=user,
            ),
            models.Source(
                uuid=uuid.uuid4(),
                name="test-source-2",
                type="ansible.eda.range",
                args={"limit": 6, "delay": 2},
                user=user,
            ),
        ]
    )

    response = client.get(f"{api_url_v1}/sources/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 2
    assert response.data["results"][0]["uuid"] == str(sources[0].uuid)
    assert response.data["results"][0]["type"] == sources[0].type
    assert response.data["results"][0]["name"] == sources[0].name
    assert response.data["results"][0]["user"] == "luke.skywalker"

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.SOURCE, Action.READ
    )


@pytest.mark.django_db
def test_retrieve_source(client: APIClient, check_permission_mock: mock.Mock):
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    source = models.Source.objects.create(
        uuid=uuid.uuid4(),
        name="test-source-1",
        type="ansible.eda.range",
        args={"limit": 5, "delay": 1},
        user=user,
    )

    response = client.get(f"{api_url_v1}/sources/{source.uuid}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == source.name
    assert response.data["type"] == source.type
    assert response.data["user"] == "luke.skywalker"

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.SOURCE, Action.READ
    )


@pytest.mark.django_db
def test_create_source(client: APIClient, check_permission_mock: mock.Mock):
    data_in = {
        "name": "test_source",
        "type": "ansible.eda.generic",
        "args": {"limit": 1, "delay": 5},
    }
    response = client.post(f"{api_url_v1}/sources/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    result = response.data
    assert result["name"] == "test_source"
    assert result["type"] == "ansible.eda.generic"
    assert result["args"] == "delay: 5\nlimit: 1"
    assert result["user"] == "test.admin"

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.SOURCE, Action.CREATE
    )
