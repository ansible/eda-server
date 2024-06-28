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
from typing import List
from urllib.parse import urlencode

import pytest
import yaml
from rest_framework import status
from rest_framework.renderers import JSONRenderer
from rest_framework.test import APIClient

from aap_eda.core import enums, models
from tests.integration.constants import api_url_v1


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
    admin_client: APIClient, default_hmac_credential: models.EdaCredential
):
    data_in = {
        "name": "test_webhook",
        "eda_credential_id": default_hmac_credential.id,
    }
    response = admin_client.post(f"{api_url_v1}/webhooks/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    result = response.data
    assert result["name"] == "test_webhook"
    assert result["owner"] == "test.admin"


@pytest.mark.django_db
def test_create_webhook_without_credentials(admin_client: APIClient):
    data_in = {
        "name": "test_webhook",
    }
    response = admin_client.post(f"{api_url_v1}/webhooks/", data=data_in)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "eda_credential_id": ["This field is required."],
    }


@pytest.mark.parametrize(
    ("hmac_algorithm", "digestmod"),
    [
        ("sha256", hashlib.sha256),
        ("sha224", hashlib.sha224),
        ("sha512", hashlib.sha512),
        ("sha3_224", hashlib.sha3_224),
        ("sha3_256", hashlib.sha3_256),
        ("sha3_384", hashlib.sha3_384),
        ("sha3_512", hashlib.sha3_512),
        ("md5", hashlib.md5),
        ("blake2b", hashlib.blake2b),
        ("blake2s", hashlib.blake2s),
    ],
)
@pytest.mark.django_db
def test_post_webhook(
    admin_client: APIClient,
    preseed_credential_types,
    hmac_algorithm,
    digestmod,
):
    secret = secrets.token_hex(32)
    signature_header_name = "My-Secret-Header"
    inputs = {
        "secret": secret,
        "header_key": signature_header_name,
        "auth_type": "hmac",
        "hmac_format": "hex",
        "hmac_algorithm": hmac_algorithm,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.HMAC.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
    }

    response = admin_client.post(f"{api_url_v1}/webhooks/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    webhook = models.Webhook.objects.get(id=response.data["id"])

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
    default_user: models.User,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    signature_header_name = "My-Secret-Header"
    inputs = {
        "secret": secret,
        "header_key": signature_header_name,
        "auth_type": "hmac",
        "hmac_format": "hex",
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.HMAC.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
    }
    response = admin_client.post(f"{api_url_v1}/webhooks/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    webhook = models.Webhook.objects.get(id=response.data["id"])

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
    default_user: models.User,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    signature_header_name = "My-Secret-Header"
    hmac_signature_prefix = "sha256="
    inputs = {
        "secret": secret,
        "header_key": signature_header_name,
        "auth_type": "hmac",
        "hmac_format": "hex",
        "hmac_signature_prefix": hmac_signature_prefix,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.HMAC.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
    }
    response = admin_client.post(f"{api_url_v1}/webhooks/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    webhook = models.Webhook.objects.get(id=response.data["id"])

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
    default_user: models.User,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    signature_header_name = "My-Secret-Header"
    hmac_signature_prefix = "sha256="
    inputs = {
        "secret": secret,
        "header_key": signature_header_name,
        "auth_type": "hmac",
        "hmac_format": "hex",
        "hmac_signature_prefix": hmac_signature_prefix,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.HMAC.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
    }
    response = admin_client.post(f"{api_url_v1}/webhooks/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    webhook = models.Webhook.objects.get(id=response.data["id"])
    data = {"a": 1, "b": 2}
    data_bytes = JSONRenderer().render(data)
    hash_object = hmac.new(
        secret.encode("utf-8"), msg=data_bytes, digestmod=hashlib.sha256
    )
    headers = {
        signature_header_name: (
            f"{hmac_signature_prefix}" f"{hash_object.hexdigest()}"
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
    default_user: models.User,
    default_webhook: models.Webhook,
):
    response = admin_client.delete(
        f"{api_url_v1}/webhooks/{default_webhook.id}/"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_post_webhook_with_bad_uuid(
    admin_client: APIClient,
    default_user: models.User,
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
    default_user: models.User,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    signature_header_name = "My-Secret-Header"
    hmac_signature_prefix = "sha256="
    inputs = {
        "secret": secret,
        "header_key": signature_header_name,
        "auth_type": "hmac",
        "hmac_format": "hex",
        "hmac_signature_prefix": hmac_signature_prefix,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.HMAC.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
    }
    response = admin_client.post(f"{api_url_v1}/webhooks/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    webhook = models.Webhook.objects.get(id=response.data["id"])
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()
    hash_object = hmac.new(
        secret.encode("utf-8"), msg=data_bytes, digestmod=hashlib.sha256
    )
    headers = {
        signature_header_name: (
            f"{hmac_signature_prefix}" f"{hash_object.hexdigest()}"
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
    default_user: models.User,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    signature_header_name = "My-Secret-Header"
    hmac_signature_prefix = "sha256="
    inputs = {
        "secret": secret,
        "header_key": signature_header_name,
        "auth_type": "hmac",
        "hmac_format": "base64",
        "hmac_signature_prefix": hmac_signature_prefix,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.HMAC.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
    }
    response = admin_client.post(f"{api_url_v1}/webhooks/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    webhook = models.Webhook.objects.get(id=response.data["id"])
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()
    hash_object = hmac.new(
        secret.encode("utf-8"), msg=data_bytes, digestmod=hashlib.sha256
    )
    b64_signature = base64.b64encode(hash_object.digest()).decode()
    headers = {
        signature_header_name: (f"{hmac_signature_prefix}" f"{b64_signature}"),
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
def test_post_webhook_with_basic_auth(
    admin_client: APIClient,
    default_user: models.User,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    username = "fred"
    signature_header_name = "Authorization"
    inputs = {
        "auth_type": "basic",
        "username": username,
        "secret": secret,
        "header_key": signature_header_name,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.BASIC.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
    }
    response = admin_client.post(f"{api_url_v1}/webhooks/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    webhook = models.Webhook.objects.get(id=response.data["id"])
    user_pass = f"{username}:{secret}"
    auth_value = f"Basic {base64.b64encode(user_pass.encode()).decode()}"
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()
    headers = {
        signature_header_name: auth_value,
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
def test_post_webhook_with_token(
    admin_client: APIClient,
    default_user: models.User,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    signature_header_name = "My-Secret-Header"
    inputs = {
        "auth_type": "token",
        "secret": secret,
        "header_key": signature_header_name,
    }

    obj = _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.TOKEN.value, inputs
    )

    data_in = {
        "name": "test-webhook-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
    }
    response = admin_client.post(f"{api_url_v1}/webhooks/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    webhook = models.Webhook.objects.get(id=response.data["id"])
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()
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
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_post_webhook_with_test_mode_extra_headers(
    admin_client: APIClient,
    default_user: models.User,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    signature_header_name = "X-Gitlab-Token"
    inputs = {
        "auth_type": "token",
        "secret": secret,
        "header_key": signature_header_name,
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
    }
    response = admin_client.post(f"{api_url_v1}/webhooks/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    webhook = models.Webhook.objects.get(id=response.data["id"])
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


@pytest.mark.django_db
def test_fetching_webhook_credential(
    admin_client: APIClient,
    default_user: models.User,
    preseed_credential_types,
):
    inputs = {
        "auth_type": "token",
        "secret": "secret",
        "header_key": "Authorization",
    }
    _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.TOKEN.value, inputs, "demo1"
    )

    inputs = {
        "auth_type": "basic",
        "secret": "secret",
        "username": "fred",
        "header_key": "Authorization",
    }
    _create_webhook_credential(
        admin_client, enums.WebhookCredentialType.BASIC.value, inputs, "demo2"
    )
    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?credential_type__kind=token"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["results"][0]["name"] == "demo1"


def _create_webhook_credential(
    client: APIClient,
    credential_type_name: str,
    inputs: dict,
    name: str = "eda-credential",
) -> dict:
    credential_type = models.CredentialType.objects.get(
        name=credential_type_name
    )
    data_in = {
        "name": name,
        "inputs": inputs,
        "credential_type_id": credential_type.id,
    }
    response = client.post(f"{api_url_v1}/eda-credentials/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()
