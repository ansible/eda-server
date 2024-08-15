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
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

__all__ = (
    "AuthenticationFailed",
    "NotAuthenticated",
    "BadRequest",
    "NotFound",
    "Conflict",
    "Unprocessable",
    "PermissionDenied",
    "api_fallback_handler",
)


def api_fallback_handler(exc, context):
    response = exception_handler(exc, context)
    if (response is None) and (not settings.DEBUG):
        response = Response(
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            data={
                "detail": (
                    "Unexpected server error"
                    "; contact your system administrator"
                )
            },
        )
        response["context"] = context
    return response


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


class NotImplemented(APIException):
    status_code = status.HTTP_501_NOT_IMPLEMENTED
    default_code = "not_implemented"
    default_detail = _("Not implemented.")


class Forbidden(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "forbidden"
    default_detail = _("Forbidden.")


class InvalidWebsocketScheme(APIException):
    status_code = 422
    default_detail = (
        "Connection Error: Invalid WebSocket URL scheme. "
        "Scheme should be either 'ws' or 'wss'."
    )


class InvalidWebsocketHost(APIException):
    status_code = 422
    default_detail = (
        "Connection Error: WebSocket URL must have a valid host address."
    )


class InvalidWebhookSource(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = (
        "Configuration Error: Webhook source could not be updated in ruleset"
    )
