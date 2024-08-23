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
import secrets

import pytest
import requests_mock
from rest_framework import status
from rest_framework.renderers import JSONRenderer
from rest_framework.test import APIClient

from aap_eda.core import enums
from tests.integration.api.test_event_stream import (
    create_event_stream,
    create_event_stream_credential,
    event_stream_post_url,
    get_default_test_org,
)


@pytest.mark.parametrize(
    ("auth_status", "payload", "post_status"),
    [
        (status.HTTP_200_OK, {"active": True}, status.HTTP_200_OK),
        (status.HTTP_403_FORBIDDEN, {"active": False}, status.HTTP_200_OK),
        (status.HTTP_403_FORBIDDEN, {"nada": False}, status.HTTP_200_OK),
        (status.HTTP_403_FORBIDDEN, "Kaboom", status.HTTP_403_FORBIDDEN),
    ],
)
@pytest.mark.django_db
def test_post_event_stream_with_oauth2(
    admin_client: APIClient,
    preseed_credential_types,
    auth_status,
    payload,
    post_status,
):
    header_key = "Authorization"
    access_token = "dummy"
    introspection_url = (
        "https://fake.com/auth/realms/eda-demo/"
        "protocol/openid-connect/token/introspect"
    )
    secret = secrets.token_hex(32)
    inputs = {
        "auth_type": "oauth2",
        "client_id": "test",
        "client_secret": secret,
        "introspection_url": introspection_url,
        "http_header_key": header_key,
    }

    obj = create_event_stream_credential(
        admin_client, enums.EventStreamCredentialType.OAUTH2.value, inputs
    )

    data_in = {
        "name": "test-es-1",
        "eda_credential_id": obj["id"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)

    data = {"a": 1, "b": 2}
    content_type = "application/json"
    data_bytes = JSONRenderer().render(data)
    headers = {
        header_key: access_token,
        "Content-Type": content_type,
    }

    with requests_mock.Mocker() as m:
        m.post(introspection_url, json=payload, status_code=post_status)
        response = admin_client.post(
            event_stream_post_url(event_stream.uuid),
            headers=headers,
            data=data_bytes,
            content_type=content_type,
        )
    assert response.status_code == auth_status
