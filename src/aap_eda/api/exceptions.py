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
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
)

__all__ = (
    "AuthenticationFailed",
    "NotAuthenticated",
    "BadRequest",
    "NotFound",
    "Conflict",
    "Unprocessable",
)


class BadRequest(APIException):
    status = status.HTTP_400_BAD_REQUEST
    default_code = "bad_request"
    default_detail = _("Bad request.")


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"
    default_detail = _("Conflict.")


class Unprocessable(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "unprocessable"
    default_detail = _("Unprocessable.")
