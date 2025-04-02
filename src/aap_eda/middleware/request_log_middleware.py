#  Copyright 2025 Red Hat, Inc.
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
import uuid
from contextvars import ContextVar

from django.utils.deprecation import MiddlewareMixin

log_tracking_id_var = ContextVar("log_tracking_id", default="")
request_id_var = ContextVar("request_id", default="")


class RequestLogMiddleware(MiddlewareMixin):
    def process_request(self, request):
        req_id = request.headers.get("X-Request-ID")

        if not req_id:
            req_id = str(uuid.uuid4())
            request.META["HTTP_X_REQUEST_ID"] = req_id
            request.__dict__.pop("headers", None)

        request.id = req_id

        request_id_var.set(req_id)

    def process_response(self, request, response):
        if hasattr(request, "id"):
            response["X-Request-ID"] = request.id
        return response


def get_request_id():
    return request_id_var.get()


def get_log_tracking_id():
    return log_tracking_id_var.get()


def assign_log_tracking_id(log_tracking_id):
    log_tracking_id_var.set(log_tracking_id)


def assign_request_id(request_id):
    request_id_var.set(request_id)
