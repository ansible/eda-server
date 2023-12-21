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

import secrets
from itertools import groupby

from rest_framework_simplejwt.tokens import RefreshToken

from aap_eda.core.models import User


def group_permission_resource(permission_data):
    grouped_permissions = []
    for key, group in groupby(
        permission_data, key=lambda x: (x["resource_type"])
    ):
        actions = [item["action"] for item in group]
        grouped_permissions.append({"resource_type": key, "action": actions})
    return grouped_permissions


def display_permissions(role_data: dict) -> dict:
    grouped_permissions = group_permission_resource(role_data["permissions"])
    role_data["permissions"] = grouped_permissions
    return role_data


def create_jwt_token() -> tuple[str, str]:
    """Create JWT access and refresh token pair.

    They can be sent to rulebook clients through command line arguments.
    """
    user, _ = User.objects.get_or_create(
        username="_token_service_user",
        is_service_account=True,
        defaults={"password": secrets.token_urlsafe()},
    )
    rf = RefreshToken.for_user(user)
    return (str(rf.access_token), str(rf))
