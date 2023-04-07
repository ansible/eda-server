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
from unittest import mock

import pytest

from aap_eda.api.permissions import RoleBasedPermission
from aap_eda.core import models
from aap_eda.core.enums import Action, ResourceType


@pytest.fixture(autouse=True)
def initial_data():
    reader_role = models.Role.objects.create(name="test-role-reader")
    reader_role.permissions.add(
        models.Permission.objects.get_or_create(
            resource_type=ResourceType.USER,
            action=Action.READ,
        )[0]
    )

    writer_role = models.Role.objects.create(name="test-role-creator")
    writer_role.permissions.add(
        models.Permission.objects.get_or_create(
            resource_type=ResourceType.USER,
            action=Action.CREATE,
        )[0]
    )

    reader_user = models.User.objects.create_user(username="test-user-reader")
    reader_user.roles.add(reader_role)

    writer_user = models.User.objects.create_user(username="test-user-creator")
    writer_user.roles.add(writer_role)


@pytest.mark.parametrize(
    ("username", "action", "decision"),
    [
        ("test-user-reader", "retrieve", True),
        ("test-user-reader", "create", False),
        ("test-user-creator", "retrieve", False),
        ("test-user-creator", "create", True),
    ],
)
@pytest.mark.django_db
def test_permissions(username: str, action: str, decision: bool):
    user = models.User.objects.get(username=username)

    request = mock.Mock(user=user)
    view = mock.Mock(
        name="TestView",
        spec=["basename", "action"],
        basename="user",
        action=action,
    )

    permission = RoleBasedPermission()
    assert permission.has_permission(request, view) == decision
