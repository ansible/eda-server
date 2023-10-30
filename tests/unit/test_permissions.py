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
from django.core.exceptions import ImproperlyConfigured

from aap_eda.api.permissions import RoleBasedPermission
from aap_eda.core.enums import Action, ResourceType


def test_superuser():
    request = mock.Mock(user=mock.Mock(is_superuser=True))
    view = mock.Mock(name="TestView", spec=[])

    permission = RoleBasedPermission()
    assert permission.has_permission(request, view) is True


def test_regular_view_zeroconf():
    request = mock.Mock(user=mock.Mock(is_superuser=False))
    view = mock.Mock(name="TestView", spec=[])

    permission = RoleBasedPermission()
    with pytest.raises(ImproperlyConfigured) as exc_info:
        assert permission.has_permission(request, view)
        assert exc_info.match(r"Cannot determine resource type for view ")


@pytest.mark.parametrize(
    ("view_action", "rbac_action"),
    [
        ("list", Action.READ),
        ("create", Action.CREATE),
        ("retrieve", Action.READ),
        ("update", Action.UPDATE),
        ("partial_update", Action.UPDATE),
        ("destroy", Action.DELETE),
    ],
)
def test_view_set_zeroconf(view_action, rbac_action):
    request = mock.Mock(user=mock.Mock(is_superuser=False))
    view = mock.Mock(
        name="TestView",
        spec=["basename", "action"],
        basename="user",
        action=view_action,
    )

    with mock.patch.object(RoleBasedPermission, "_check_permission", mock.Mock(return_value=True)) as check_method:
        permission = RoleBasedPermission()
        assert permission.has_permission(request, view) is True

        check_method.assert_called_once_with(request.user, ResourceType.USER, rbac_action)


def test_view_set_unknown_resource_type():
    request = mock.Mock(user=mock.Mock(is_superuser=False))
    view = mock.Mock(
        name="TestView",
        spec=["basename", "action"],
        basename="unknown",
        action="retrieve",
    )

    permission = RoleBasedPermission()
    with pytest.raises(ImproperlyConfigured) as exc_info:
        permission.has_permission(request, view)
        exc_info.match("Cannot resolve basename into permission resource type for view ")


def test_view_set_unknown_action():
    request = mock.Mock(user=mock.Mock(is_superuser=False))
    view = mock.Mock(
        name="TestView",
        spec=["basename", "action"],
        basename="user",
        action="unknown",
    )

    permission = RoleBasedPermission()
    with pytest.raises(ImproperlyConfigured) as exc_info:
        permission.has_permission(request, view)
        exc_info.match("Cannot resolve view action into permission action for view ")


def test_view_set_override_resource_type():
    request = mock.Mock(user=mock.Mock(is_superuser=False))
    view = mock.Mock(
        name="TestView",
        spec=["basename", "action", "rbac_resource_type"],
        basename="unknown",
        action="retrieve",
        rbac_resource_type=ResourceType.USER,
    )

    with mock.patch.object(RoleBasedPermission, "_check_permission", mock.Mock(return_value=True)) as check_method:
        permission = RoleBasedPermission()
        assert permission.has_permission(request, view) is True

        check_method.assert_called_once_with(request.user, ResourceType.USER, Action.READ)


def test_view_set_override_action():
    request = mock.Mock(user=mock.Mock(is_superuser=False))
    view = mock.Mock(
        name="TestView",
        spec=["basename", "action", "rbac_action"],
        basename="user",
        action="unknown",
        rbac_action=Action.READ,
    )

    with mock.patch.object(RoleBasedPermission, "_check_permission", mock.Mock(return_value=True)) as check_method:
        permission = RoleBasedPermission()
        assert permission.has_permission(request, view) is True

        check_method.assert_called_once_with(request.user, ResourceType.USER, Action.READ)


def test_view_set_override_resource_type_and_action():
    request = mock.Mock(user=mock.Mock(is_superuser=False))
    view = mock.Mock(
        name="TestView",
        spec=["basename", "action", "rbac_resource_type", "rbac_action"],
        basename="unknown",
        action="unknown",
        rbac_resource_type=ResourceType.USER,
        rbac_action=Action.READ,
    )

    with mock.patch.object(RoleBasedPermission, "_check_permission", mock.Mock(return_value=True)) as check_method:
        permission = RoleBasedPermission()
        assert permission.has_permission(request, view) is True

        check_method.assert_called_once_with(request.user, ResourceType.USER, Action.READ)


def test_view_set_override_get_permission():
    request = mock.Mock(user=mock.Mock(is_superuser=False))
    get_rbac_permission = mock.Mock(return_value=(ResourceType.USER, Action.READ))
    view = mock.Mock(
        name="TestView",
        spec=["basename", "action", "get_rbac_permission"],
        basename="unknown",
        action="unknown",
        get_rbac_permission=get_rbac_permission,
    )

    with mock.patch.object(RoleBasedPermission, "_check_permission", mock.Mock(return_value=True)) as check_method:
        permission = RoleBasedPermission()
        assert permission.has_permission(request, view) is True

        get_rbac_permission.assert_called_once_with()
        check_method.assert_called_once_with(request.user, ResourceType.USER, Action.READ)
