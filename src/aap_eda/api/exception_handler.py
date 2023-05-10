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

from rest_framework.views import exception_handler as base_exception_handler

from .exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
)

EXCEPTIONS_WITH_CODE = (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
)


def exception_handler(exc, context):
    response = base_exception_handler(exc, context)
    if response is None:
        return response
    response.data["code"] = None
    if isinstance(exc, EXCEPTIONS_WITH_CODE):
        response.data["code"] = exc.detail.code
    return response
