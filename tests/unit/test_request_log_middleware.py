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

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from aap_eda.middleware.request_log_middleware import (
    RequestLogMiddleware,
    assign_log_tracking_id,
    assign_request_id,
    get_log_tracking_id,
    get_request_id,
    log_tracking_id_var,
    request_id_var,
)


@pytest.fixture(autouse=True)
def context_vars_cleanup():
    req_token = request_id_var.set("")
    log_token = log_tracking_id_var.set("")

    yield

    request_id_var.reset(req_token)
    log_tracking_id_var.reset(log_token)


@pytest.fixture
def middleware():
    return RequestLogMiddleware(get_response=lambda r: HttpResponse())


@pytest.fixture
def request_obj():
    return RequestFactory().get("/")


def test_process_request_with_header(middleware, request_obj):
    test_id = "test-request"
    request_obj.headers = {"X-Request-ID": test_id}

    middleware.process_request(request_obj)

    assert request_obj.id == test_id
    assert get_request_id() == test_id


def test_process_request_without_header(middleware, request_obj):
    request_obj.headers = {}

    middleware.process_request(request_obj)

    assert request_obj.id == ""
    assert get_request_id() == ""


def test_process_response(middleware, request_obj):
    test_id = "test-response"
    request_obj.id = test_id
    response = HttpResponse()

    result = middleware.process_response(request_obj, response)

    assert result["X-Request-ID"] == test_id


def test_get_set_request_id():
    test_id = "test-context"
    assign_request_id(test_id)
    assert get_request_id() == test_id


def test_get_set_log_tracking_id():
    test_id = "test-tracking"
    assign_log_tracking_id(test_id)
    assert get_log_tracking_id() == test_id


def test_default_values():
    assert get_request_id() == ""
    assert get_log_tracking_id() == ""
