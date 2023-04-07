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
from __future__ import annotations

import typing
from typing import Optional, Tuple

from django.core.exceptions import ImproperlyConfigured
from rest_framework import permissions
from rest_framework.request import Request

from aap_eda.core import models
from aap_eda.core.enums import Action, ResourceType

# NOTE(cutwater): Conditional import is required to avoid circular imports.
if typing.TYPE_CHECKING:
    from rest_framework.views import APIView

__all__ = ("RoleBasedPermission",)


class RoleBasedPermission(permissions.BasePermission):
    """
    Allow user to perform an action on resource based on their roles.

    This class implements role based access control (RBAC) for views.
    A permission check is successful if a user has a relevant permission
    in the set of their roles. A permission is a pair of a resource type
    and an action.

    Normally for each view a resource type and action are determined
    automatically based on view "basename" and "action" attributes.
    The view "basename" attribute is set based on a model name used in
    view's queryset.

    The view actions are translated into permission actions as following:
        * list -> read
        * create -> create
        * retrieve -> read
        * update -> update
        * partial_update -> update
        * destroy -> delete

    For custom action you need to specify ``rbac_action`` attribute
    for a view set. Example::

        class ExampleViewSet(ModelViewSet):
            queryset = ExampleModel.objects.all()

            rbac_action = None  # Setting attribute on class level is required
                                # to override it in @action decorator

            @action(methods=["POST"], rbac_action=Action.UPDATE)
            def custom_action(self, request, *args, **kwargs):
                ...

    In case model cannot be mapped into resource type, you can set
    the ``rbac_resource_type`` attribute for a view set the similar to
    ``rbac_action`` attribute.

    For more sophisticated resource type or action you may define a method
    ``get_rbac_permission`` that returns a tuple of ResourceType and Action::

        class ExampleViewSet(ModelViewSet):
            queryset = ExampleModel.objects.all()

            def get_rbac_permission(self):
                if self.action == "foo":
                    return ResourceType.FOO, Action.CREATE
                else:
                    return ResourceType.FOO, Action.READ
    """

    action_map = {
        "list": Action.READ,
        "create": Action.CREATE,
        "retrieve": Action.READ,
        "update": Action.UPDATE,
        "partial_update": Action.UPDATE,
        "destroy": Action.DELETE,
    }

    def has_permission(self, request: Request, view: APIView):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        permission = self._get_permission(view)
        if permission is None:
            return False

        resource_type, action = permission
        return self._check_permission(request.user, resource_type, action)

    def _get_permission(
        self, view: APIView
    ) -> Optional[Tuple[ResourceType, Action]]:
        view_permission_func = getattr(view, "get_rbac_permission", None)
        if view_permission_func is not None:
            resource_type, action = view_permission_func()
        else:
            resource_type = self._get_resource_type(view)
            action = self._get_action(view)
            if action is None:
                return None

        return resource_type, action

    def _get_resource_type(self, view: APIView) -> ResourceType:
        resource_type = getattr(view, "rbac_resource_type", None)

        if resource_type is not None:
            return resource_type

        if hasattr(view, "basename"):
            try:
                return ResourceType(view.basename)
            except ValueError:
                raise ImproperlyConfigured(
                    f"Cannot resolve basename into permission resource type "
                    f'for view "{view}". Set "rbac_resource_type" attribute '
                    f'or implement "get_rbac_permission" method.'
                )

        raise ImproperlyConfigured(
            f'Cannot determine resource type for view "{view}". '
            f'Set "rbac_resource_type" attribute or implement '
            f'"get_rbac_permission" method.'
        )

    def _get_action(self, view: APIView) -> Optional[Action]:
        action = getattr(view, "rbac_action", None)
        if action is not None:
            return action

        if hasattr(view, "action"):
            if view.action is None:
                return None
            try:
                action = self.action_map[view.action]
            except KeyError:
                raise ImproperlyConfigured(
                    f"Cannot resolve view action into permission action "
                    f'for view "{view}". Set "rbac_action" attribute or'
                    f'implement "get_rbac_permission" method.'
                )
        return action

    def _check_permission(
        self, user: models.User, resource_type: ResourceType, action: Action
    ) -> bool:
        return models.Permission.objects.filter(
            roles__users=user,
            resource_type=resource_type,
            action=action,
        ).exists()
