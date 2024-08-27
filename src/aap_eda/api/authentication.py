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

from rest_framework.authentication import (
    BaseAuthentication,
    SessionAuthentication as _SessionAuthentication,
)
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from aap_eda.services.auth import validate_jwt_token
from aap_eda.services.exceptions import InvalidTokenError


class SessionAuthentication(_SessionAuthentication):
    """Custom session authentication class.

    This is a workaround for DRF returning 403 Forbidden status code instead
    of 401 Unauthorized for session authentication, that does not define
    an appropriate `WWW-Authenticate` header value.
    """

    def authenticate_header(self, request):
        return "Session"


class WebsocketJWTAuthentication(BaseAuthentication):
    def authenticate(self, request: Request):
        header = request.META.get("HTTP_AUTHORIZATION")
        if not header:
            return None

        parts = header.split()
        if len(parts) == 0 or parts[0] != "Bearer":
            return None

        if len(parts) > 2:
            raise AuthenticationFailed("Invalid Bearer token format")

        try:
            return validate_jwt_token(parts[1], "access"), None
        except InvalidTokenError as e:
            raise AuthenticationFailed("Invalid token") from e
