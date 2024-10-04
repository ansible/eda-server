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
from urllib.parse import urlencode

import pytest
import yaml
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import enums
from tests.integration.api.test_event_stream import (
    create_event_stream,
    create_event_stream_credential,
    event_stream_post_url,
    get_default_test_org,
)


@pytest.mark.parametrize(
    ("auth_status", "bogus_token"),
    [
        (status.HTTP_200_OK, None),
        (status.HTTP_403_FORBIDDEN, "bogus"),
    ],
)
@pytest.mark.django_db
def test_post_event_stream_with_token(
    admin_client: APIClient,
    preseed_credential_types,
    auth_status,
    bogus_token,
):
    secret = secrets.token_hex(32)
    signature_header_name = "My-Secret-Header"
    inputs = {
        "auth_type": "token",
        "token": secret,
        "http_header_key": signature_header_name,
    }

    obj = create_event_stream_credential(
        admin_client, enums.EventStreamCredentialType.TOKEN.value, inputs
    )

    data_in = {
        "name": "test-es-1",
        "eda_credential_id": obj["id"],
        "event_stream_type": obj["credential_type"]["kind"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()
    if bogus_token:
        secret = bogus_token
    headers = {
        signature_header_name: secret,
        "Content-Type": content_type,
    }
    response = admin_client.post(
        event_stream_post_url(event_stream.uuid),
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == auth_status


@pytest.mark.django_db
def test_post_event_stream_with_test_mode_extra_headers(
    admin_client: APIClient,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    signature_header_name = "X-Gitlab-Token"
    inputs = {
        "auth_type": "token",
        "token": secret,
        "http_header_key": signature_header_name,
    }

    obj = create_event_stream_credential(
        admin_client, enums.EventStreamCredentialType.TOKEN.value, inputs
    )

    additional_data_headers = (
        "X-Gitlab-Event,X-Gitlab-Event-Uuid,X-Gitlab-Uuid"
    )
    data_in = {
        "name": "test-es-1",
        "eda_credential_id": obj["id"],
        "event_stream_type": obj["credential_type"]["kind"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
        "additional_data_headers": additional_data_headers,
    }
    event_stream = create_event_stream(admin_client, data_in)
    data = {"a": 1, "b": 2}
    headers = {
        "X-Gitlab-Event-Uuid": "c2675c66-7e6e-4fe2-9ac3-288534ef34b9",
        "X-Gitlab-Instance": "https://gitlab.com",
        signature_header_name: secret,
        "X-Gitlab-Uuid": "b697868f-3b59-4a1f-985d-47f79e2b05ff",
        "X-Gitlab-Event": "Push Hook",
    }

    response = admin_client.post(
        event_stream_post_url(event_stream.uuid),
        headers=headers,
        data=data,
    )
    assert response.status_code == status.HTTP_200_OK

    event_stream.refresh_from_db()
    test_data = yaml.safe_load(event_stream.test_content)
    assert test_data["a"] == 1
    assert test_data["b"] == 2
    test_headers = yaml.safe_load(event_stream.test_headers)
    assert (
        test_headers["X-Gitlab-Event-Uuid"]
        == "c2675c66-7e6e-4fe2-9ac3-288534ef34b9"
    )
    assert (
        test_headers["X-Gitlab-Uuid"] == "b697868f-3b59-4a1f-985d-47f79e2b05ff"
    )
    assert test_headers["X-Gitlab-Event"] == "Push Hook"
    assert event_stream.test_content_type == "application/json"
    assert event_stream.events_received == 1
    assert event_stream.last_event_received_at is not None
