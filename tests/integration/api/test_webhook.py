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
import uuid
from datetime import datetime
from typing import List
from unittest.mock import patch
from urllib.parse import urlencode

import jwt
import pytest
import requests_mock
import yaml
from django.conf import settings
from django.test import override_settings
from ecdsa import SigningKey
from ecdsa.util import sigencode_der
from rest_framework import status
from rest_framework.renderers import JSONRenderer
from rest_framework.test import APIClient

from aap_eda.core import enums, models
from tests.integration.constants import api_url_v1

ECDSA_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEfBis6O6gsIb2Xk6Q82CcEJcwOw+j
hkmGJmzauR5LXaRmek9rwJpO0FhJ01rirMMyVazm0o3S91VS6WEps66UVg==
-----END PUBLIC KEY-----"""  # notsecret

ECDSA_PRIVATE_KEY = """-----BEGIN EC PRIVATE KEY-----
MHcCAQEEID7fDPE0/HavFrQx2F7/+hBTT8mCqI9dn+rSRnce6SwfoAoGCCqGSM49
AwEHoUQDQgAEfBis6O6gsIb2Xk6Q82CcEJcwOw+jhkmGJmzauR5LXaRmek9rwJpO
0FhJ01rirMMyVazm0o3S91VS6WEps66UVg==
-----END EC PRIVATE KEY-----"""  # notsecret


@pytest.mark.django_db
def test_list_webhooks(
    admin_client: APIClient,
    default_webhooks: List[models.Webhook],
    default_vault_credential,
):
    response = admin_client.get(f"{api_url_v1}/webhooks/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 2
    assert response.data["results"][0]["name"] == default_webhooks[0].name
    assert response.data["results"][0]["owner"] == "luke.skywalker"


@pytest.mark.django_db
def test_retrieve_webhook(
    admin_client: APIClient,
    default_webhooks: List[models.Webhook],
    default_vault_credential,
):
    webhook = default_webhooks[0]
    response = admin_client.get(f"{api_url_v1}/webhooks/{webhook.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == default_webhooks[0].name
    assert response.data["url"] == default_webhooks[0].url
    assert response.data["owner"] == "luke.skywalker"


@pytest.mark.django_db
def test_create_webhook(
    admin_client: APIClient,
    default_hmac_credential: models.EdaCredential,
    default_organization: models.Organization,
):
    data_in = {
        "name": "test_webhook",
        "eda_credential_id": default_hmac_credential.id,
        "organization_id": default_organization.id,
    }
    webhook = _create_webhook(admin_client, data_in)
    assert webhook.name == "test_webhook"
    assert webhook.owner.username == "test.admin"


@pytest.mark.django_db
def test_create_webhook_without_credentials(
    admin_client: APIClient,
    default_organization: models.Organization,
):
    data_in = {
        "name": "test_webhook",
        "organization_id": default_organization.id,
    }
    response = admin_client.post(f"{api_url_v1}/webhooks/", data=data_in)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "eda_credential_id": ["This field is required."],
    }


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
def test_post_webhook(
    admin_client: APIClient,
    preseed_credential_types,
    hash_algorithm,
    digestmod,
    default_organization: models.Organization,
):
    secret = secrets.token_hex(32)
    signature_header_name = "My-Secret-Header"
    inputs = {
        "secret": secret,
        "http_header_key": signature_header_name,
        "auth_type": "hmac",
        "signature_encoding": "hex",
        "hash_algorithm": hash_algorithm,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.HMAC.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "organization_id": default_organization.id,
    }

    webhook = _create_webhook(admin_client, data_in)

    data = {"a": 1, "b": 2}
    data_bytes = JSONRenderer().render(data)
    hash_object = hmac.new(
        secret.encode("utf-8"), msg=data_bytes, digestmod=digestmod
    )
    headers = {signature_header_name: hash_object.hexdigest()}
    response = admin_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_post_webhook_bad_secret(
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    secret = secrets.token_hex(32)
    signature_header_name = "My-Secret-Header"
    inputs = {
        "secret": secret,
        "http_header_key": signature_header_name,
        "auth_type": "hmac",
        "signature_encoding": "hex",
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.HMAC.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "organization_id": default_organization.id,
    }
    webhook = _create_webhook(admin_client, data_in)
    bad_secret = secrets.token_hex(32)
    data = {"a": 1, "b": 2}
    data_bytes = JSONRenderer().render(data)
    hash_object = hmac.new(
        bad_secret.encode("utf-8"), msg=data_bytes, digestmod=hashlib.sha256
    )
    headers = {signature_header_name: hash_object.hexdigest()}
    response = admin_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    webhook.refresh_from_db()
    assert (
        webhook.test_error_message
        == "Signature mismatch, check your payload and secret"
    )


@pytest.mark.django_db
def test_post_webhook_with_prefix(
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    secret = secrets.token_hex(32)
    signature_header_name = "My-Secret-Header"
    hmac_signature_prefix = "sha256="
    inputs = {
        "secret": secret,
        "http_header_key": signature_header_name,
        "auth_type": "hmac",
        "signature_encoding": "hex",
        "signature_prefix": hmac_signature_prefix,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.HMAC.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "organization_id": default_organization.id,
    }
    webhook = _create_webhook(admin_client, data_in)
    data = {"a": 1, "b": 2}
    data_bytes = JSONRenderer().render(data)
    hash_object = hmac.new(
        secret.encode("utf-8"), msg=data_bytes, digestmod=hashlib.sha256
    )
    headers = {
        signature_header_name: f"{hmac_signature_prefix}"
        f"{hash_object.hexdigest()}"
    }
    response = admin_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_post_webhook_with_test_mode(
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    secret = secrets.token_hex(32)
    signature_header_name = "My-Secret-Header"
    hmac_signature_prefix = "sha256="
    inputs = {
        "secret": secret,
        "http_header_key": signature_header_name,
        "auth_type": "hmac",
        "signature_encoding": "hex",
        "signature_prefix": hmac_signature_prefix,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.HMAC.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "organization_id": default_organization.id,
    }
    webhook = _create_webhook(admin_client, data_in)
    data = {"a": 1, "b": 2}
    data_bytes = JSONRenderer().render(data)
    hash_object = hmac.new(
        secret.encode("utf-8"), msg=data_bytes, digestmod=hashlib.sha256
    )
    headers = {
        signature_header_name: (
            f"{hmac_signature_prefix}{hash_object.hexdigest()}"
        )
    }
    response = admin_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data,
    )
    assert response.status_code == status.HTTP_200_OK

    webhook.refresh_from_db()
    test_data = yaml.safe_load(webhook.test_content)
    assert test_data["a"] == 1
    assert test_data["b"] == 2
    assert webhook.test_content_type == "application/json"


@pytest.mark.django_db
def test_delete_webhook(
    admin_client: APIClient,
    default_webhook: models.Webhook,
):
    response = admin_client.delete(
        f"{api_url_v1}/webhooks/{default_webhook.id}/"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_delete_webhook_with_exception(
    admin_client: APIClient,
    default_activation: models.Activation,
    default_webhook: models.Webhook,
):
    activation = default_activation
    activation.webhooks.add(default_webhook)

    response = admin_client.delete(
        f"{api_url_v1}/webhooks/{default_webhook.id}/"
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        f"Event stream '{default_webhook.name}' is being referenced by "
        "1 activation(s) and cannot be deleted"
    ) in response.data["detail"]


@pytest.mark.django_db
def test_post_webhook_with_bad_uuid(
    admin_client: APIClient,
    default_webhook: models.Webhook,
):
    data = {"a": 1, "b": 2}
    response = admin_client.post(
        f"{api_url_v1}/external_webhook/{str(uuid.uuid4())}/post/",
        data=data,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_post_webhook_with_form_urlencoded(
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    secret = secrets.token_hex(32)
    signature_header_name = "My-Secret-Header"
    hmac_signature_prefix = "sha256="
    inputs = {
        "secret": secret,
        "http_header_key": signature_header_name,
        "auth_type": "hmac",
        "signature_encoding": "hex",
        "signature_prefix": hmac_signature_prefix,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.HMAC.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "organization_id": default_organization.id,
    }
    webhook = _create_webhook(admin_client, data_in)
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()
    hash_object = hmac.new(
        secret.encode("utf-8"), msg=data_bytes, digestmod=hashlib.sha256
    )
    headers = {
        signature_header_name: (
            f"{hmac_signature_prefix}{hash_object.hexdigest()}"
        ),
        "Content-Type": content_type,
    }
    response = admin_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_post_webhook_with_base64_format(
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    secret = secrets.token_hex(32)
    signature_header_name = "My-Secret-Header"
    hmac_signature_prefix = "sha256="
    inputs = {
        "secret": secret,
        "http_header_key": signature_header_name,
        "auth_type": "hmac",
        "signature_encoding": "base64",
        "signature_prefix": hmac_signature_prefix,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.HMAC.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "organization_id": default_organization.id,
    }
    webhook = _create_webhook(admin_client, data_in)
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()
    hash_object = hmac.new(
        secret.encode("utf-8"), msg=data_bytes, digestmod=hashlib.sha256
    )
    b64_signature = base64.b64encode(hash_object.digest()).decode()
    headers = {
        signature_header_name: f"{hmac_signature_prefix}{b64_signature}",
        "Content-Type": content_type,
    }
    response = admin_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.parametrize(
    ("auth_status", "bogus_password"),
    [
        (status.HTTP_200_OK, None),
        (status.HTTP_403_FORBIDDEN, "bogus"),
    ],
)
@pytest.mark.django_db
def test_post_webhook_with_basic_auth(
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
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

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.BASIC.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "organization_id": default_organization.id,
    }
    webhook = _create_webhook(admin_client, data_in)
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
    response = admin_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == auth_status


@pytest.mark.parametrize(
    ("auth_status", "bogus_token"),
    [
        (status.HTTP_200_OK, None),
        (status.HTTP_403_FORBIDDEN, "bogus"),
    ],
)
@pytest.mark.django_db
def test_post_webhook_with_token(
    admin_client: APIClient,
    default_organization: models.Organization,
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

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.TOKEN.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "organization_id": default_organization.id,
    }
    webhook = _create_webhook(admin_client, data_in)
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
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == auth_status


@pytest.mark.django_db
def test_post_webhook_with_test_mode_extra_headers(
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    secret = secrets.token_hex(32)
    signature_header_name = "X-Gitlab-Token"
    inputs = {
        "auth_type": "token",
        "token": secret,
        "http_header_key": signature_header_name,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.TOKEN.value, inputs
    )

    additional_data_headers = (
        "X-Gitlab-Event,X-Gitlab-Event-Uuid,X-Gitlab-Webhook-Uuid"
    )
    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "additional_data_headers": additional_data_headers,
        "organization_id": default_organization.id,
    }
    webhook = _create_webhook(admin_client, data_in)
    data = {"a": 1, "b": 2}
    headers = {
        "X-Gitlab-Event-Uuid": "c2675c66-7e6e-4fe2-9ac3-288534ef34b9",
        "X-Gitlab-Instance": "https://gitlab.com",
        signature_header_name: secret,
        "X-Gitlab-Webhook-Uuid": "b697868f-3b59-4a1f-985d-47f79e2b05ff",
        "X-Gitlab-Event": "Push Hook",
    }

    response = admin_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data,
    )
    assert response.status_code == status.HTTP_200_OK

    webhook.refresh_from_db()
    test_data = yaml.safe_load(webhook.test_content)
    assert test_data["a"] == 1
    assert test_data["b"] == 2
    test_headers = yaml.safe_load(webhook.test_headers)
    assert (
        test_headers["X-Gitlab-Event-Uuid"]
        == "c2675c66-7e6e-4fe2-9ac3-288534ef34b9"
    )
    assert (
        test_headers["X-Gitlab-Webhook-Uuid"]
        == "b697868f-3b59-4a1f-985d-47f79e2b05ff"
    )
    assert test_headers["X-Gitlab-Event"] == "Push Hook"
    assert webhook.test_content_type == "application/json"
    assert webhook.events_received == 1
    assert webhook.last_event_received_at is not None


@pytest.mark.parametrize(
    ("auth_status", "data", "bogus_data", "signature_encoding"),
    [
        (status.HTTP_200_OK, {"a": 1, "b": 2}, None, "hex"),
        (status.HTTP_200_OK, {"a": 1, "b": 2}, None, "base64"),
        (status.HTTP_403_FORBIDDEN, {"a": 1, "b": 2}, {"x": 1}, "hex"),
        (status.HTTP_403_FORBIDDEN, {"a": 1, "b": 2}, {"x": 1}, "base64"),
    ],
)
@pytest.mark.django_db
def test_post_webhook_with_ecdsa(
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
    auth_status,
    data,
    bogus_data,
    signature_encoding,
):
    signature_header_name = "My-Ecdsa-Sig"
    inputs = {
        "auth_type": "ecdsa",
        "public_key": ECDSA_PUBLIC_KEY,
        "http_header_key": signature_header_name,
        "signature_encoding": signature_encoding,
        "hash_algorithm": "sha256",
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.ECDSA.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "organization_id": default_organization.id,
    }
    webhook = _create_webhook(admin_client, data_in)
    content_type = "application/json"
    data_bytes = JSONRenderer().render(data)
    sk = SigningKey.from_pem(ECDSA_PRIVATE_KEY, hashlib.sha256)
    signature = sk.sign_deterministic(data_bytes, sigencode=sigencode_der)
    if signature_encoding == "base64":
        signature_str = base64.b64encode(signature).decode()
    else:
        signature_str = signature.hex()

    headers = {
        signature_header_name: signature_str,
        "Content-Type": content_type,
    }
    if bogus_data:
        data_bytes = JSONRenderer().render(bogus_data)
    response = admin_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == auth_status


@pytest.mark.django_db
def test_post_webhook_with_ecdsa_with_prefix(
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    signature_header_name = "My-Ecdsa-Sig"
    prefix_header_name = "My-Ecdsa-Prefix"
    content_prefix = datetime.now().isoformat()
    signature_encoding = "base64"
    inputs = {
        "auth_type": "ecdsa",
        "public_key": ECDSA_PUBLIC_KEY,
        "http_header_key": signature_header_name,
        "signature_encoding": signature_encoding,
        "hash_algorithm": "sha256",
        "prefix_http_header_key": prefix_header_name,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.ECDSA.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "organization_id": default_organization.id,
    }
    webhook = _create_webhook(admin_client, data_in)

    content_type = "application/json"
    data = {"a": 1, "b": 2}
    message_bytes = bytearray()
    message_bytes.extend(content_prefix.encode())
    data_bytes = JSONRenderer().render(data)
    message_bytes.extend(data_bytes)

    sk = SigningKey.from_pem(ECDSA_PRIVATE_KEY, hashlib.sha256)
    signature = sk.sign_deterministic(message_bytes, sigencode=sigencode_der)
    signature_str = base64.b64encode(signature).decode()
    headers = {
        signature_header_name: signature_str,
        prefix_header_name: content_prefix,
        "Content-Type": content_type,
    }
    response = admin_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_fetching_webhook_credential(
    admin_client: APIClient,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    inputs = {
        "auth_type": "token",
        "token": secret,
        "http_header_key": "Authorization",
    }
    _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.TOKEN.value, inputs, "demo1"
    )

    inputs = {
        "auth_type": "basic",
        "password": secret,
        "username": "fred",
        "http_header_key": "Authorization",
    }
    _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.BASIC.value, inputs, "demo2"
    )
    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?credential_type__kind=token"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["results"][0]["name"] == "demo1"


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
def test_post_webhook_with_oauth2(
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
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

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.OAUTH2.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "organization_id": default_organization.id,
    }
    webhook = _create_webhook(admin_client, data_in)

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
            f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
            headers=headers,
            data=data_bytes,
            content_type=content_type,
        )
    assert response.status_code == auth_status


@pytest.mark.parametrize(
    ("auth_status", "side_effect"),
    [
        (status.HTTP_200_OK, None),
        (status.HTTP_403_FORBIDDEN, jwt.exceptions.PyJWTError("Kaboom")),
    ],
)
@pytest.mark.django_db
def test_post_webhook_with_oauth2_jwt(
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
    auth_status,
    side_effect,
):
    header_key = "Authorization"
    access_token = "dummy"
    jwks_url = "https://my_as_server/.well-known/jwks.json"
    audience = "dummy"
    inputs = {
        "auth_type": "oauth2-jwt",
        "jwks_url": jwks_url,
        "audience": audience,
        "http_header_key": header_key,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.OAUTH2_JWT.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "organization_id": default_organization.id,
    }
    webhook = _create_webhook(admin_client, data_in)

    data = {"a": 1, "b": 2}
    content_type = "application/json"
    data_bytes = JSONRenderer().render(data)
    headers = {
        header_key: f"Bearer {access_token}",
        "Content-Type": content_type,
    }
    with patch("aap_eda.api.webhook_authentication.PyJWKClient"):
        with patch(
            "aap_eda.api.webhook_authentication.jwt_decode",
            side_effect=side_effect,
        ):
            response = admin_client.post(
                f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
                headers=headers,
                data=data_bytes,
                content_type=content_type,
            )
    assert response.status_code == auth_status


@pytest.mark.parametrize(
    ("auth_status", "subject", "bogus_subject"),
    [
        (status.HTTP_200_OK, "subject", None),
        (status.HTTP_403_FORBIDDEN, "subject", "bogus"),
    ],
)
@pytest.mark.django_db
def test_post_webhook_with_mtls(
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
    subject,
    auth_status,
    bogus_subject,
):
    header_key = "Subject"
    inputs = {
        "auth_type": "mtls",
        "subject": subject,
        "http_header_key": header_key,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.MTLS.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "organization_id": default_organization.id,
    }
    webhook = _create_webhook(admin_client, data_in)
    data = {"a": 1, "b": 2}
    content_type = "application/json"
    data_bytes = JSONRenderer().render(data)
    if bogus_subject:
        subject = bogus_subject

    headers = {
        header_key: subject,
        "Content-Type": content_type,
    }
    response = admin_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == auth_status


@pytest.mark.django_db
def test_post_webhook_with_mtls_missing_settings(
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    header_key = "Subject"
    inputs = {
        "auth_type": "mtls",
        "subject": "Subject",
        "http_header_key": header_key,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.MTLS.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "organization_id": default_organization.id,
    }
    with override_settings(WEBHOOK_MTLS_BASE_URL=None):
        response = admin_client.post(f"{api_url_v1}/webhooks/", data=data_in)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "eda_credential_id": [
                (
                    "EventStream of type mTLS Webhook cannot be "
                    "used because WEBHOOK_MTLS_BASE_URL is "
                    "missing in settings."
                )
            ]
        }


@pytest.mark.django_db
def test_post_webhook_with_basic_auth_missing_settings(
    admin_client: APIClient,
    preseed_credential_types,
    default_organization: models.Organization,
):
    secret = secrets.token_hex(32)
    username = "fred"
    inputs = {
        "auth_type": "basic",
        "username": username,
        "password": secret,
        "http_header_key": "Authorization",
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.BASIC.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "organization_id": default_organization.id,
    }
    with override_settings(WEBHOOK_BASE_URL=None):
        response = admin_client.post(f"{api_url_v1}/webhooks/", data=data_in)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "eda_credential_id": [
                (
                    "EventStream of type Basic Webhook cannot be used because "
                    "WEBHOOK_BASE_URL is missing in settings."
                )
            ]
        }


def _create_webhook_credential(
    client: APIClient,
    credential_type_name: str,
    inputs: dict,
    name: str = "eda-credential",
) -> dict:
    credential_type = models.CredentialType.objects.get(
        name=credential_type_name
    )
    organization = models.Organization.objects.get_or_create(
        name=settings.DEFAULT_ORGANIZATION_NAME,
        description="The default organization",
    )[0]
    data_in = {
        "name": name,
        "inputs": inputs,
        "credential_type_id": credential_type.id,
        "organization_id": organization.id,
    }
    response = client.post(f"{api_url_v1}/eda-credentials/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


def _create_webhook(client: APIClient, data_in: dict) -> models.Webhook:
    with override_settings(
        WEBHOOK_BASE_URL="https://www.example.com/",
        WEBHOOK_MTLS_BASE_URL="https://www.example.com/",
    ):
        response = client.post(f"{api_url_v1}/webhooks/", data=data_in)
        assert response.status_code == status.HTTP_201_CREATED
        return models.Webhook.objects.get(id=response.data["id"])
