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
import base64
import secrets
from urllib.parse import urlencode

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import enums, models
from tests.integration.api.test_event_stream import (
    create_event_stream,
    create_event_stream_credential,
    event_stream_post_url,
    get_default_test_org,
)


@pytest.mark.parametrize(
    ("auth_status", "bogus_password"),
    [
        (status.HTTP_200_OK, None),
        (status.HTTP_403_FORBIDDEN, "bogus"),
    ],
)
@pytest.mark.django_db
def test_post_event_stream_with_basic_auth(
    base_client: APIClient,
    admin_user: models.User,
    anonymous_user: models.User,
    preseed_credential_types,
    auth_status,
    bogus_password,
):
    secret = secrets.token_hex(32)
    username = "fred"
    inputs = {
        "auth_type": "basic",
        "username": username,
        "password": secret,
        "http_header_key": "Authorization",
    }

    base_client.force_authenticate(user=admin_user)
    obj = create_event_stream_credential(
        base_client, enums.EventStreamCredentialType.BASIC.value, inputs
    )

    data_in = {
        "name": "test-es-1",
        "eda_credential_id": obj["id"],
        "event_stream_type": obj["credential_type"]["kind"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(base_client, data_in)
    if bogus_password:
        user_pass = f"{username}:{bogus_password}"
    else:
        user_pass = f"{username}:{secret}"

    auth_value = f"Basic {base64.b64encode(user_pass.encode()).decode()}"
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()
    headers = {
        "Authorization": auth_value,
        "Content-Type": content_type,
    }
    response = base_client.post(
        event_stream_post_url(event_stream.uuid),
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == auth_status

    base_client.force_authenticate(user=anonymous_user)
    response = base_client.post(
        event_stream_post_url(event_stream.uuid),
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == auth_status


@pytest.mark.parametrize(
    ("content_type", "status"),
    [
        ("application/json", status.HTTP_400_BAD_REQUEST),
        ("application/x-www-form-urlencoded", status.HTTP_400_BAD_REQUEST),
    ],
)
@pytest.mark.django_db
def test_post_event_stream_with_basic_auth_bad_encoding(
    admin_client: APIClient, preseed_credential_types, content_type, status
):
    secret = secrets.token_hex(32)
    username = "fred"
    inputs = {
        "auth_type": "basic",
        "username": username,
        "password": secret,
        "http_header_key": "Authorization",
    }

    obj = create_event_stream_credential(
        admin_client, enums.EventStreamCredentialType.BASIC.value, inputs
    )

    data_in = {
        "name": "test-es-1",
        "eda_credential_id": obj["id"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)
    user_pass = f"{username}:{secret}"

    auth_value = f"Basic {base64.b64encode(user_pass.encode()).decode()}"
    data_bytes = '{"a": 1,'.encode()
    headers = {
        "Authorization": auth_value,
        "Content-Type": content_type,
    }
    response = admin_client.post(
        event_stream_post_url(event_stream.uuid),
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == status
