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
from uuid import uuid4

import pytest
from ansible_base.rbac import permission_registry
from ansible_base.rbac.models import DABPermission, RoleDefinition
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models

api_url_v1 = "/api/eda/v1"


def grant_obj_perm(user, obj, action):
    content_type = (
        permission_registry.content_type_model.objects.get_for_model(obj)
    )
    role = RoleDefinition.objects.create(
        name=f"log-purge-{action}-{uuid4()}",
        content_type=content_type,
    )
    permissions = [
        DABPermission.objects.get(codename=f"{action}_{obj._meta.model_name}")
    ]
    if action != "view":
        permissions.append(
            DABPermission.objects.get(codename=f"view_{obj._meta.model_name}")
        )
    role.permissions.add(*permissions)
    role.give_permission(user, obj)


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
def test_clear_logs_per_activation_instance_only_selected_instance(
    default_activation_instances: List[models.RulebookProcess],
    default_activation_instance_logs: List[models.RulebookProcessLog],
    new_activation_instance: models.RulebookProcess,
    admin_client: APIClient,
):
    selected_instance = default_activation_instances[0]
    sibling_instance = default_activation_instances[1]
    sibling_log = models.RulebookProcessLog.objects.create(
        log="sibling-log",
        activation_instance=sibling_instance,
        log_timestamp=1000,
    )
    other_activation_log = models.RulebookProcessLog.objects.create(
        log="other-activation-log",
        activation_instance=new_activation_instance,
        log_timestamp=1000,
    )
    selected_count = models.RulebookProcessLog.objects.filter(
        activation_instance=selected_instance,
    ).count()

    response = admin_client.post(
        f"{api_url_v1}/activation-instances/{selected_instance.id}"
        "/clear-logs/",
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"deleted": selected_count}
    assert not models.RulebookProcessLog.objects.filter(
        activation_instance=selected_instance,
    ).exists()
    assert models.RulebookProcessLog.objects.filter(pk=sibling_log.pk).exists()
    assert models.RulebookProcessLog.objects.filter(
        pk=other_activation_log.pk,
    ).exists()


@pytest.mark.django_db
def test_clear_logs_per_activation_instance_with_before_date(
    default_activation_instances: List[models.RulebookProcess],
    default_activation_instance_logs: List[models.RulebookProcessLog],
    new_activation_instance: models.RulebookProcess,
    admin_client: APIClient,
):
    selected_instance = default_activation_instances[0]
    sibling_instance = default_activation_instances[1]
    selected_old_log = models.RulebookProcessLog.objects.get(
        activation_instance=selected_instance,
        log_timestamp=1000,
    )
    sibling_log = models.RulebookProcessLog.objects.create(
        log="sibling-old-log",
        activation_instance=sibling_instance,
        log_timestamp=1000,
    )
    other_activation_log = models.RulebookProcessLog.objects.create(
        log="other-activation-old-log",
        activation_instance=new_activation_instance,
        log_timestamp=1000,
    )

    response = admin_client.post(
        f"{api_url_v1}/activation-instances/{selected_instance.id}"
        "/clear-logs/",
        data={"before_date": "1970-01-01T00:25:00Z"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"deleted": 1}
    assert not models.RulebookProcessLog.objects.filter(
        pk=selected_old_log.pk,
    ).exists()
    assert models.RulebookProcessLog.objects.filter(
        activation_instance=selected_instance,
        log_timestamp=2000,
    ).exists()
    assert models.RulebookProcessLog.objects.filter(pk=sibling_log.pk).exists()
    assert models.RulebookProcessLog.objects.filter(
        pk=other_activation_log.pk,
    ).exists()


@pytest.mark.django_db
def test_clear_logs_per_activation_instance_not_found(admin_client: APIClient):
    response = admin_client.post(
        f"{api_url_v1}/activation-instances/999999/clear-logs/",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_clear_logs_per_activation_instance_requires_instance_access(
    default_activation_instances: List[models.RulebookProcess],
    default_activation_instance_logs: List[models.RulebookProcessLog],
    user_client: APIClient,
):
    instance = default_activation_instances[0]

    response = user_client.post(
        f"{api_url_v1}/activation-instances/{instance.id}/clear-logs/",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert (
        models.RulebookProcessLog.objects.filter(
            activation_instance=instance,
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_clear_logs_per_activation_instance_requires_activation_delete(
    default_activation: models.Activation,
    default_activation_instances: List[models.RulebookProcess],
    default_activation_instance_logs: List[models.RulebookProcessLog],
    default_user,
    user_client: APIClient,
):
    instance = default_activation_instances[0]
    grant_obj_perm(default_user, instance, "view")

    response = user_client.post(
        f"{api_url_v1}/activation-instances/{instance.id}/clear-logs/",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert (
        models.RulebookProcessLog.objects.filter(
            activation_instance=instance,
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_clear_logs_per_activation_instance_allows_activation_delete(
    default_activation: models.Activation,
    default_activation_instances: List[models.RulebookProcess],
    default_activation_instance_logs: List[models.RulebookProcessLog],
    default_user,
    user_client: APIClient,
):
    instance = default_activation_instances[0]
    grant_obj_perm(default_user, instance, "view")
    grant_obj_perm(default_user, default_activation, "delete")

    response = user_client.post(
        f"{api_url_v1}/activation-instances/{instance.id}/clear-logs/",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"deleted": 2}
    assert not models.RulebookProcessLog.objects.filter(
        activation_instance=instance,
    ).exists()


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
