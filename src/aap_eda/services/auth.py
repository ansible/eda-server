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

from datetime import datetime, timedelta
from itertools import groupby

import jwt
from ansible_base.resource_registry.signals.handlers import no_reverse_sync
from django.conf import settings

from aap_eda.core.models.user import User
from aap_eda.services.exceptions import InvalidTokenError


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


JWT_ALGORITHM = "HS256"


def create_jwt_token() -> tuple[str, str]:
    """Create JWT access and refresh token pair.

    They can be sent to rulebook clients through command line arguments.
    """
    with no_reverse_sync():
        user, new = User.objects.get_or_create(
            username="_token_service_user",
            is_service_account=True,
        )
    if new:
        user.set_unusable_password()
        user.save(update_fields=["password"])

    access_token = jwt_access_token(user.id)
    refresh_token = jwt_refresh_token(user.id)
    return (access_token, refresh_token)


def jwt_access_token(user_id: int) -> str:
    expiration = timedelta(
        minutes=float(settings.JWT_ACCESS_TOKEN_LIFETIME_MINUTES)
    )
    return get_jwt_token(user_id, expiration, token_type="access")


def jwt_refresh_token(user_id: int) -> str:
    expiration = timedelta(
        days=float(settings.JWT_REFRESH_TOKEN_LIFETIME_DAYS)
    )
    return get_jwt_token(user_id, expiration, token_type="refresh")


def get_jwt_token(user_id, expiration, **kwargs):
    payload = {
        "user_id": user_id,
        "exp": datetime.now() + expiration,
        **kwargs,
    }

    return jwt.encode(payload, settings.SECRET_KEY, JWT_ALGORITHM)


def parse_jwt_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, JWT_ALGORITHM)
    except jwt.DecodeError as e:
        raise InvalidTokenError("Bad token") from e
    except jwt.ExpiredSignatureError as e:
        raise InvalidTokenError("Expired token") from e


def validate_jwt_token(token: str, token_type: str) -> User:
    token_dict = parse_jwt_token(token)

    for key in ["user_id", "exp", "token_type"]:
        if key not in token_dict:
            raise InvalidTokenError("Missing key in token")

    if token_dict["token_type"] != token_type:
        raise InvalidTokenError("Invalid token type")

    try:
        return User.objects.get(id=token_dict["user_id"])
    except User.DoesNotExist as e:
        raise InvalidTokenError("Invalid user") from e
