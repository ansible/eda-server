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
import hashlib
from datetime import datetime

import pytest
from ecdsa import SigningKey
from ecdsa.util import sigencode_der
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

ECDSA_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEfBis6O6gsIb2Xk6Q82CcEJcwOw+j
hkmGJmzauR5LXaRmek9rwJpO0FhJ01rirMMyVazm0o3S91VS6WEps66UVg==
-----END PUBLIC KEY-----"""  # notsecret

ECDSA_PRIVATE_KEY = """-----BEGIN EC PRIVATE KEY-----
MHcCAQEEID7fDPE0/HavFrQx2F7/+hBTT8mCqI9dn+rSRnce6SwfoAoGCCqGSM49
AwEHoUQDQgAEfBis6O6gsIb2Xk6Q82CcEJcwOw+jhkmGJmzauR5LXaRmek9rwJpO
0FhJ01rirMMyVazm0o3S91VS6WEps66UVg==
-----END EC PRIVATE KEY-----"""  # notsecret


@pytest.mark.parametrize(
    ("auth_status", "data", "bogus_data", "signature_encoding", "use_prefix"),
    [
        (status.HTTP_200_OK, {"a": 1, "b": 2}, None, "hex", False),
        (status.HTTP_200_OK, {"a": 1, "b": 2}, None, "base64", False),
        (status.HTTP_200_OK, {"a": 1, "b": 2}, None, "hex", True),
        (status.HTTP_200_OK, {"a": 1, "b": 2}, None, "base64", True),
        (status.HTTP_403_FORBIDDEN, {"a": 1, "b": 2}, {"x": 1}, "hex", False),
        (
            status.HTTP_403_FORBIDDEN,
            {"a": 1, "b": 2},
            {"x": 1},
            "base64",
            False,
        ),
    ],
)
@pytest.mark.django_db
def test_post_event_stream_with_ecdsa(
    admin_client: APIClient,
    preseed_credential_types,
    auth_status,
    data,
    bogus_data,
    signature_encoding,
    use_prefix,
):
    signature_header_name = "My-Ecdsa-Sig"
    prefix_header_name = "My-Ecdsa-Prefix"
    content_prefix = datetime.now().isoformat()
    inputs = {
        "auth_type": "ecdsa",
        "public_key": ECDSA_PUBLIC_KEY,
        "http_header_key": signature_header_name,
        "signature_encoding": signature_encoding,
        "hash_algorithm": "sha256",
    }

    if use_prefix:
        inputs["prefix_http_header_key"] = prefix_header_name

    obj = create_event_stream_credential(
        admin_client, enums.EventStreamCredentialType.ECDSA.value, inputs
    )

    data_in = {
        "name": "test-es-1",
        "eda_credential_id": obj["id"],
        "event_stream_type": obj["credential_type"]["kind"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)
    content_type = "application/json"

    message_bytes = bytearray()
    if use_prefix:
        message_bytes.extend(content_prefix.encode())
        data_bytes = JSONRenderer().render(data)
        message_bytes.extend(data_bytes)
    else:
        data_bytes = JSONRenderer().render(data)
        message_bytes.extend(data_bytes)

    sk = SigningKey.from_pem(ECDSA_PRIVATE_KEY, hashlib.sha256)
    signature = sk.sign_deterministic(message_bytes, sigencode=sigencode_der)
    if signature_encoding == "base64":
        signature_str = base64.b64encode(signature).decode()
    else:
        signature_str = signature.hex()

    headers = {
        signature_header_name: signature_str,
        "Content-Type": content_type,
    }
    if use_prefix:
        headers[prefix_header_name] = content_prefix

    if bogus_data:
        data_bytes = JSONRenderer().render(bogus_data)
    response = admin_client.post(
        event_stream_post_url(event_stream.uuid),
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == auth_status
