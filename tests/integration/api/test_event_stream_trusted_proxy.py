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

"""Tests for X-Trusted-Proxy header validation in external event stream."""

import secrets
from urllib.parse import urlencode

import pytest
from ansible_base.jwt_consumer.common.util import (
    generate_x_trusted_proxy_header,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test.utils import override_settings
from freezegun import freeze_time
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import enums
from tests.integration.api.test_event_stream import (
    create_event_stream,
    create_event_stream_credential,
    event_stream_post_url,
    get_default_test_org,
)


@pytest.fixture
def test_rsa_keypair():
    """Generate an RSA keypair for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048
    )
    public_key = private_key.public_key()
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return {"private": private_key_bytes, "public": public_key_bytes}


@pytest.mark.django_db
def test_post_event_stream_with_valid_trusted_proxy_header(
    admin_client: APIClient,
    preseed_credential_types,
    test_rsa_keypair,
):
    """Test that a valid X-Trusted-Proxy header allows the request."""
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

    data_in = {
        "name": "test-es-trusted-proxy-valid",
        "eda_credential_id": obj["id"],
        "event_stream_type": obj["credential_type"]["kind"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()

    # Generate valid X-Trusted-Proxy header
    with override_settings(ANSIBLE_BASE_JWT_KEY=test_rsa_keypair["public"]):
        trusted_proxy_header = generate_x_trusted_proxy_header(
            test_rsa_keypair["private"]
        )

        headers = {
            signature_header_name: secret,
            "Content-Type": content_type,
            "X-Trusted-Proxy": trusted_proxy_header,
        }

        response = admin_client.post(
            event_stream_post_url(event_stream.uuid),
            headers=headers,
            data=data_bytes,
            content_type=content_type,
        )
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_post_event_stream_without_trusted_proxy_validation_disabled(
    admin_client: APIClient,
    preseed_credential_types,
    test_rsa_keypair,
):
    """Test requests work without X-Trusted-Proxy when disabled."""
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

    data_in = {
        "name": "test-es-trusted-proxy-disabled",
        "eda_credential_id": obj["id"],
        "event_stream_type": obj["credential_type"]["kind"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()

    # Disable X-Trusted-Proxy validation
    with override_settings(EVENT_STREAM_REQUIRE_TRUSTED_PROXY=False):
        headers = {
            signature_header_name: secret,
            "Content-Type": content_type,
            # X-Trusted-Proxy header is intentionally missing
        }

        response = admin_client.post(
            event_stream_post_url(event_stream.uuid),
            headers=headers,
            data=data_bytes,
            content_type=content_type,
        )
        # Should succeed when validation is disabled
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_post_event_stream_missing_trusted_proxy_header(
    admin_client: APIClient,
    preseed_credential_types,
    test_rsa_keypair,
):
    """Test that a missing X-Trusted-Proxy header results in 400."""
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

    data_in = {
        "name": "test-es-trusted-proxy-missing",
        "eda_credential_id": obj["id"],
        "event_stream_type": obj["credential_type"]["kind"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()

    with override_settings(ANSIBLE_BASE_JWT_KEY=test_rsa_keypair["public"]):
        headers = {
            signature_header_name: secret,
            "Content-Type": content_type,
            # X-Trusted-Proxy header is intentionally missing
        }

        response = admin_client.post(
            event_stream_post_url(event_stream.uuid),
            headers=headers,
            data=data_bytes,
            content_type=content_type,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert b"Invalid request" in response.content


@pytest.mark.django_db
def test_post_event_stream_invalid_trusted_proxy_header(
    admin_client: APIClient,
    preseed_credential_types,
    test_rsa_keypair,
):
    """Test that an invalid X-Trusted-Proxy header results in 400."""
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

    data_in = {
        "name": "test-es-trusted-proxy-invalid",
        "eda_credential_id": obj["id"],
        "event_stream_type": obj["credential_type"]["kind"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()

    with override_settings(ANSIBLE_BASE_JWT_KEY=test_rsa_keypair["public"]):
        headers = {
            signature_header_name: secret,
            "Content-Type": content_type,
            # Invalid X-Trusted-Proxy header
            "X-Trusted-Proxy": "invalid-header-value",
        }

        response = admin_client.post(
            event_stream_post_url(event_stream.uuid),
            headers=headers,
            data=data_bytes,
            content_type=content_type,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert b"Invalid request" in response.content


@pytest.mark.django_db
def test_post_event_stream_expired_trusted_proxy_header(
    admin_client: APIClient,
    preseed_credential_types,
    test_rsa_keypair,
):
    """Test that an expired X-Trusted-Proxy header results in 400."""
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

    data_in = {
        "name": "test-es-trusted-proxy-expired",
        "eda_credential_id": obj["id"],
        "event_stream_type": obj["credential_type"]["kind"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()

    # Generate valid X-Trusted-Proxy header
    with override_settings(ANSIBLE_BASE_JWT_KEY=test_rsa_keypair["public"]):
        # Freeze time to generate a header with a known timestamp
        with freeze_time("2026-06-25 12:00:00") as frozen_time:
            trusted_proxy_header = generate_x_trusted_proxy_header(
                test_rsa_keypair["private"]
            )

            # Move time forward by 1.1 seconds to expire the header
            # (default timeout is 1000ms)
            frozen_time.tick(delta=1.1)

            headers = {
                signature_header_name: secret,
                "Content-Type": content_type,
                "X-Trusted-Proxy": trusted_proxy_header,
            }

            response = admin_client.post(
                event_stream_post_url(event_stream.uuid),
                headers=headers,
                data=data_bytes,
                content_type=content_type,
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert b"Invalid request" in response.content


@pytest.mark.django_db
def test_post_event_stream_wrong_signature_trusted_proxy_header(
    admin_client: APIClient,
    preseed_credential_types,
    test_rsa_keypair,
):
    """Test that a header signed with wrong key results in 400."""
    # Generate a different keypair for signing
    wrong_private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048
    )
    wrong_private_key_bytes = wrong_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

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

    data_in = {
        "name": "test-es-trusted-proxy-wrong-sig",
        "eda_credential_id": obj["id"],
        "event_stream_type": obj["credential_type"]["kind"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()

    # Generate header with wrong key but validate with the correct public key
    with override_settings(ANSIBLE_BASE_JWT_KEY=test_rsa_keypair["public"]):
        # Sign with wrong private key
        trusted_proxy_header = generate_x_trusted_proxy_header(
            wrong_private_key_bytes
        )

        headers = {
            signature_header_name: secret,
            "Content-Type": content_type,
            "X-Trusted-Proxy": trusted_proxy_header,
        }

        response = admin_client.post(
            event_stream_post_url(event_stream.uuid),
            headers=headers,
            data=data_bytes,
            content_type=content_type,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert b"Invalid request" in response.content


@pytest.mark.django_db
def test_post_event_stream_malformed_trusted_proxy_header(
    admin_client: APIClient,
    preseed_credential_types,
    test_rsa_keypair,
):
    """Test that a malformed X-Trusted-Proxy header results in 400."""
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

    data_in = {
        "name": "test-es-trusted-proxy-malformed",
        "eda_credential_id": obj["id"],
        "event_stream_type": obj["credential_type"]["kind"],
        "organization_id": get_default_test_org().id,
        "test_mode": True,
    }
    event_stream = create_event_stream(admin_client, data_in)
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()

    with override_settings(ANSIBLE_BASE_JWT_KEY=test_rsa_keypair["public"]):
        headers = {
            signature_header_name: secret,
            "Content-Type": content_type,
            # Malformed header (missing the dash separator)
            "X-Trusted-Proxy": "malformed_no_dash",
        }

        response = admin_client.post(
            event_stream_post_url(event_stream.uuid),
            headers=headers,
            data=data_bytes,
            content_type=content_type,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert b"Invalid request" in response.content
