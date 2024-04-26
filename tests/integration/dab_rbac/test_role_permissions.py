#  Copyright 2024 Red Hat, Inc.
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
from ansible_base.rbac.models import RoleDefinition, RoleUserAssignment
from django.contrib.contenttypes.models import ContentType
from rest_framework.reverse import reverse

from aap_eda.core import models


@pytest.fixture
def view_activation_rd():
    return RoleDefinition.objects.create_from_permissions(
        name="view_act",
        content_type=ContentType.objects.get_for_model(models.Activation),
        permissions=["view_activation"],
    )


@pytest.mark.django_db
def test_view_assignments_non_admin(
    user, user_api_client, cls_factory, view_activation_rd
):
    activation = cls_factory.create(models.Activation)
    assignment = view_activation_rd.give_permission(user, activation)
    url = reverse("roleuserassignment-list")
    r = user_api_client.get(url)
    assert r.status_code == 200
    assert r.data["count"] == 1
    response_obj = r.data["results"][0]
    assert response_obj["id"] == assignment.id
    assert response_obj["summary_fields"]["content_object"] == {
        "id": activation.id,
        "name": activation.name,
    }


@pytest.mark.django_db
def test_activation_assignment_non_admin(
    user_api_client, user, cls_factory, initial_data
):
    rando = models.User.objects.create(username="rando")

    # Add rando and user to same organization so they can see each other
    org = models.Organization.objects.first()
    org_member_rd = RoleDefinition.objects.get(name="Organization Member")
    for u in (rando, user):
        org_member_rd.give_permission(u, org)

    rd = RoleDefinition.objects.get(name="Activation Admin")
    activation = cls_factory.create(models.Activation)
    rd.give_permission(user, activation)
    list_url = reverse("roleuserassignment-list")
    response = user_api_client.post(
        list_url,
        data={
            "user": rando.id,
            "role_definition": rd.id,
            "object_id": activation.id,
        },
    )
    assert response.status_code == 201, response.data
    assignment = RoleUserAssignment.objects.get(
        user=rando, role_definition=rd, object_id=activation.id
    )

    # assert user can see the assignment
    detail_url = reverse(
        "roleuserassignment-detail", kwargs={"pk": assignment.id}
    )
    response = user_api_client.get(detail_url)
    assert response.data["id"] == assignment.id, response.data

    # assert permission can be removed
    response = user_api_client.delete(detail_url)
    assert response.status_code == 204, response.data


@pytest.mark.skip(reason="Not fixed in DAB")
@pytest.mark.django_db
def test_delete_user_after_assignment(user, view_activation_rd, cls_factory):
    activation = cls_factory.create(models.Activation)
    view_activation_rd.give_permission(user, activation)
    user.delete()
