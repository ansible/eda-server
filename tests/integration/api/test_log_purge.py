#  Copyright 2025 Red Hat, Inc.
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

from typing import List

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models

api_url_v1 = "/api/eda/v1"


@pytest.mark.django_db
def test_clear_logs_per_activation(
    default_activation: models.Activation,
    default_activation_instances: List[models.RulebookProcess],
    default_activation_instance_logs: List[models.RulebookProcessLog],
    admin_client: APIClient,
):
    activation_id = default_activation.id
    initial_count = models.RulebookProcessLog.objects.filter(
        activation_instance__activation_id=activation_id,
    ).count()
    assert initial_count > 0

    response = admin_client.post(
        f"{api_url_v1}/activations/{activation_id}/clear-logs/"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["deleted"] == initial_count

    remaining = models.RulebookProcessLog.objects.filter(
        activation_instance__activation_id=activation_id,
    ).count()
    assert remaining == 0


@pytest.mark.django_db
def test_clear_logs_with_before_date(
    default_activation: models.Activation,
    default_activation_instances: List[models.RulebookProcess],
    default_activation_instance_logs: List[models.RulebookProcessLog],
    admin_client: APIClient,
):
    activation_id = default_activation.id
    response = admin_client.post(
        f"{api_url_v1}/activations/{activation_id}/clear-logs/",
        data={"before_date": "1970-01-01T00:17:00Z"},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["deleted"] == 1

    remaining = models.RulebookProcessLog.objects.filter(
        activation_instance__activation_id=activation_id,
    ).count()
    assert remaining == 1


@pytest.mark.django_db
def test_clear_logs_without_date_deletes_all(
    default_activation: models.Activation,
    default_activation_instances: List[models.RulebookProcess],
    default_activation_instance_logs: List[models.RulebookProcessLog],
    admin_client: APIClient,
):
    activation_id = default_activation.id
    response = admin_client.post(
        f"{api_url_v1}/activations/{activation_id}/clear-logs/",
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["deleted"] == 2


@pytest.mark.django_db
def test_purge_global(
    default_activation_instances: List[models.RulebookProcess],
    default_activation_instance_logs: List[models.RulebookProcessLog],
    superuser_client: APIClient,
):
    initial_count = models.RulebookProcessLog.objects.count()
    assert initial_count > 0

    response = superuser_client.post(
        f"{api_url_v1}/logs/purge/",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["deleted"] == initial_count
    assert models.RulebookProcessLog.objects.count() == 0


@pytest.mark.django_db
def test_purge_global_requires_superuser(
    default_activation_instance_logs: List[models.RulebookProcessLog],
    admin_client: APIClient,
):
    response = admin_client.post(
        f"{api_url_v1}/logs/purge/",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_purge_returns_deleted_count(
    default_activation_instances: List[models.RulebookProcess],
    default_activation_instance_logs: List[models.RulebookProcessLog],
    superuser_client: APIClient,
):
    response = superuser_client.post(
        f"{api_url_v1}/logs/purge/",
    )
    assert response.status_code == status.HTTP_200_OK
    assert "deleted" in response.data
    assert isinstance(response.data["deleted"], int)
    assert response.data["deleted"] >= 0
