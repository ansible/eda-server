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
import hmac
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
    hash_digest,
)

DEFAULT_TEST_HMAC_HEADER = "My-Secret-Header"
DEFAULT_TEST_HMAC_ENCODING = "hex"
DEFAULT_TEST_HMAC_ALGORITHM = "sha256"


@pytest.mark.parametrize(
    ("hash_algorithm", "digestmod"),
    [
        ("sha256", hashlib.sha256),
        ("sha512", hashlib.sha512),
        ("sha3_224", hashlib.sha3_224),
        ("sha3_256", hashlib.sha3_256),
        ("sha3_384", hashlib.sha3_384),
        ("sha3_512", hashlib.sha3_512),
        ("blake2b", hashlib.blake2b),
        ("blake2s", hashlib.blake2s),
    ],
)
@pytest.mark.django_db
def test_post_event_stream(
    admin_client: APIClient,
    preseed_credential_types,
    hash_algorithm,
    digestmod,
):
    secret = secrets.token_hex(32)
    obj = _create_hmac_credential(admin_client, secret, hash_algorithm)
    data_in = {
        "name": "test-es-1",
        "eda_credential_id": obj["id"],
        "organization_id": get_default_test_org().id,
    }

    event_stream = create_event_stream(admin_client, data_in)

    data = {"a": 1, "b": 2}
    headers = {DEFAULT_TEST_HMAC_HEADER: hash_digest(data, secret, digestmod)}
    response = admin_client.post(
        event_stream_post_url(event_stream.uuid),
        headers=headers,
        data=data,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_post_event_stream_bad_secret(
    admin_client: APIClient,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    obj = _create_hmac_credential(admin_client, secret)
    data_in = {
        "name": "test-es-1",
        "eda_credential_id": obj["id"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)
    bad_secret = secrets.token_hex(32)
    data = {"a": 1, "b": 2}
    headers = {
        DEFAULT_TEST_HMAC_HEADER: hash_digest(data, bad_secret, hashlib.sha256)
    }
    response = admin_client.post(
        event_stream_post_url(event_stream.uuid),
        headers=headers,
        data=data,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    event_stream.refresh_from_db()
    assert (
        event_stream.test_error_message
        == "Signature mismatch, check your payload and secret"
    )


@pytest.mark.django_db
def test_post_event_stream_with_prefix(
    admin_client: APIClient,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    signature_prefix = "sha256="
    obj = _create_hmac_credential(
        admin_client,
        secret,
        DEFAULT_TEST_HMAC_ALGORITHM,
        DEFAULT_TEST_HMAC_HEADER,
        DEFAULT_TEST_HMAC_ENCODING,
        signature_prefix,
    )

    data_in = {
        "name": "test-es-1",
        "eda_credential_id": obj["id"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)
    data = {"a": 1, "b": 2}
    digest = hash_digest(data, secret, hashlib.sha256)
    headers = {DEFAULT_TEST_HMAC_HEADER: f"{signature_prefix}{digest}"}
    response = admin_client.post(
        event_stream_post_url(event_stream.uuid),
        headers=headers,
        data=data,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_post_event_stream_with_test_mode(
    admin_client: APIClient,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    signature_prefix = "sha256="
    obj = _create_hmac_credential(
        admin_client,
        secret,
        DEFAULT_TEST_HMAC_ALGORITHM,
        DEFAULT_TEST_HMAC_HEADER,
        DEFAULT_TEST_HMAC_ENCODING,
        signature_prefix,
    )
    data_in = {
        "name": "test-es-1",
        "eda_credential_id": obj["id"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)
    data = {"a": 1, "b": 2}
    digest = hash_digest(data, secret, hashlib.sha256)
    headers = {DEFAULT_TEST_HMAC_HEADER: (f"{signature_prefix}{digest}")}
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
    assert event_stream.test_content_type == "application/json"


@pytest.mark.django_db
def test_post_event_stream_with_form_urlencoded(
    admin_client: APIClient,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    signature_prefix = "sha256="
    obj = _create_hmac_credential(
        admin_client,
        secret,
        DEFAULT_TEST_HMAC_ALGORITHM,
        DEFAULT_TEST_HMAC_HEADER,
        DEFAULT_TEST_HMAC_ENCODING,
        signature_prefix,
    )

    data_in = {
        "name": "test-es-1",
        "eda_credential_id": obj["id"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()
    hash_object = hmac.new(
        secret.encode("utf-8"), msg=data_bytes, digestmod=hashlib.sha256
    )
    headers = {
        DEFAULT_TEST_HMAC_HEADER: (
            f"{signature_prefix}{hash_object.hexdigest()}"
        ),
        "Content-Type": content_type,
    }
    response = admin_client.post(
        event_stream_post_url(event_stream.uuid),
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_post_event_stream_with_base64_format(
    admin_client: APIClient,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    signature_prefix = "sha256="
    obj = _create_hmac_credential(
        admin_client,
        secret,
        DEFAULT_TEST_HMAC_ALGORITHM,
        DEFAULT_TEST_HMAC_HEADER,
        "base64",
        signature_prefix,
    )
    data_in = {
        "name": "test-es-1",
        "eda_credential_id": obj["id"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()
    hash_object = hmac.new(
        secret.encode("utf-8"), msg=data_bytes, digestmod=hashlib.sha256
    )
    b64_signature = base64.b64encode(hash_object.digest()).decode()
    headers = {
        DEFAULT_TEST_HMAC_HEADER: f"{signature_prefix}{b64_signature}",
        "Content-Type": content_type,
    }
    response = admin_client.post(
        event_stream_post_url(event_stream.uuid),
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == status.HTTP_200_OK


def _create_hmac_credential(
    admin_client,
    secret: str,
    hash_algorithm: str = DEFAULT_TEST_HMAC_ALGORITHM,
    signature_header_name: str = DEFAULT_TEST_HMAC_HEADER,
    signature_encoding: str = DEFAULT_TEST_HMAC_ENCODING,
    signature_prefix: str = "",
) -> dict:
    inputs = {
        "secret": secret,
        "http_header_key": signature_header_name,
        "auth_type": "hmac",
        "signature_encoding": signature_encoding,
        "hash_algorithm": hash_algorithm,
    }
    if signature_prefix:
        inputs["signature_prefix"] = signature_prefix

    return create_event_stream_credential(
        admin_client, enums.EventStreamCredentialType.HMAC.value, inputs
    )
