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
from unittest import mock
from urllib.parse import urlencode

import pytest
import yaml
from rest_framework import status
from rest_framework.renderers import JSONRenderer
from rest_framework.test import APIClient

from aap_eda.core import models
from aap_eda.core.enums import Action, ResourceType
from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_list_webhooks(
    client: APIClient,
    check_permission_mock: mock.Mock,
    default_user: models.User,
):
    webhooks = models.Webhook.objects.bulk_create(
        [
            models.Webhook(
                uuid=uuid.uuid4(),
                name="test-webhook-1",
                owner=default_user,
                url="http://www.example.com",
                secret="secret",
            ),
            models.Webhook(
                uuid=uuid.uuid4(),
                name="test-webhook-2",
                owner=default_user,
                url="http://www.example.com",
                secret="secret",
            ),
        ]
    )

    response = client.get(f"{api_url_v1}/webhooks/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 2
    assert response.data["results"][0]["name"] == webhooks[0].name
    assert response.data["results"][0]["owner"] == "luke.skywalker"

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.WEBHOOK, Action.READ
    )


@pytest.mark.django_db
def test_retrieve_webhook(
    client: APIClient,
    check_permission_mock: mock.Mock,
    default_user: models.User,
):
    webhook = models.Webhook.objects.create(
        uuid=uuid.uuid4(),
        name="test-webhook-1",
        owner=default_user,
        url="http://www.example.com",
        secret="secret",
    )

    response = client.get(f"{api_url_v1}/webhooks/{webhook.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == webhook.name
    assert response.data["url"] == webhook.url
    assert response.data["owner"] == "luke.skywalker"

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.WEBHOOK, Action.READ
    )


@pytest.mark.django_db
def test_create_webhook(
    client: APIClient,
    check_permission_mock: mock.Mock,
):
    data_in = {
        "name": "test_webhook",
        "header_key": "xyz",
        "hmac_signature_prefix": "xyz=",
        "secret": "some secret value",
    }
    response = client.post(f"{api_url_v1}/webhooks/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    result = response.data
    assert result["name"] == "test_webhook"
    assert result["owner"] == "test.admin"
    assert result["header_key"] == "xyz"
    assert result["hmac_signature_prefix"] == "xyz="

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.WEBHOOK, Action.CREATE
    )


@pytest.mark.django_db
def test_post_webhook(
    base_client: APIClient,
    check_permission_mock: mock.Mock,
    default_user: models.User,
):
    secret = secrets.token_hex(32)
    signature_header_name = "my-secret-header"
    webhook = models.Webhook.objects.create(
        uuid=uuid.uuid4(),
        name="test-webhook-1",
        owner=default_user,
        url="http://www.example.com",
        secret=secret,
        header_key=signature_header_name,
    )
    data = {"a": 1, "b": 2}
    data_bytes = JSONRenderer().render(data)
    hash_object = hmac.new(
        secret.encode("utf-8"), msg=data_bytes, digestmod=hashlib.sha256
    )
    headers = {signature_header_name: hash_object.hexdigest()}
    response = base_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_post_webhook_bad_secret(
    base_client: APIClient,
    check_permission_mock: mock.Mock,
    default_user: models.User,
):
    secret = secrets.token_hex(32)
    signature_header_name = "my-secret-header"
    webhook = models.Webhook.objects.create(
        uuid=uuid.uuid4(),
        name="test-webhook-1",
        owner=default_user,
        url="http://www.example.com",
        secret=secret,
        header_key=signature_header_name,
        test_mode=True,
    )
    bad_secret = secrets.token_hex(32)
    data = {"a": 1, "b": 2}
    data_bytes = JSONRenderer().render(data)
    hash_object = hmac.new(
        bad_secret.encode("utf-8"), msg=data_bytes, digestmod=hashlib.sha256
    )
    headers = {signature_header_name: hash_object.hexdigest()}
    response = base_client.post(
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
    base_client: APIClient,
    check_permission_mock: mock.Mock,
    default_user: models.User,
):
    secret = secrets.token_hex(32)
    signature_header_name = "my-secret-header"
    hmac_signature_prefix = "sha256="
    webhook = models.Webhook.objects.create(
        uuid=uuid.uuid4(),
        name="test-webhook-1",
        owner=default_user,
        url="http://www.example.com",
        secret=secret,
        header_key=signature_header_name,
        hmac_signature_prefix=hmac_signature_prefix,
    )
    data = {"a": 1, "b": 2}
    data_bytes = JSONRenderer().render(data)
    hash_object = hmac.new(
        secret.encode("utf-8"), msg=data_bytes, digestmod=hashlib.sha256
    )
    headers = {
        signature_header_name: f"{hmac_signature_prefix}"
        f"{hash_object.hexdigest()}"
    }
    response = base_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_post_webhook_with_test_mode(
    base_client: APIClient,
    check_permission_mock: mock.Mock,
    default_user: models.User,
):
    secret = secrets.token_hex(32)
    signature_header_name = "my-secret-header"
    hmac_signature_prefix = "sha256="
    webhook = models.Webhook.objects.create(
        uuid=uuid.uuid4(),
        name="test-webhook-1",
        owner=default_user,
        url="http://www.example.com",
        secret=secret,
        header_key=signature_header_name,
        hmac_signature_prefix=hmac_signature_prefix,
        test_mode=True,
    )
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
    response = base_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data,
    )
    assert response.status_code == status.HTTP_200_OK

    webhook.refresh_from_db()
    test_data = yaml.safe_load(webhook.test_content)
    assert test_data["a"] == 1
    assert test_data["b"] == 2
    assert test_data["eda_webhook_name"] == "test-webhook-1"
    assert webhook.test_content_type == "application/json"


@pytest.mark.django_db
def test_create_webhook_bad_algorithm(
    client: APIClient,
    check_permission_mock: mock.Mock,
):
    data_in = {
        "name": "test_webhook",
        "header_key": "xyz",
        "hmac_signature_prefix": "xyz=",
        "hmac_algorithm": "nada",
    }
    response = client.post(f"{api_url_v1}/webhooks/", data=data_in)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    result = response.data
    assert "Invalid hash algorithm nada" in str(result["hmac_algorithm"][0])


@pytest.mark.django_db
def test_create_webhook_bad_format(
    client: APIClient,
    check_permission_mock: mock.Mock,
):
    data_in = {
        "name": "test_webhook",
        "header_key": "xyz",
        "hmac_signature_prefix": "xyz=",
        "hmac_format": "nada",
    }
    response = client.post(f"{api_url_v1}/webhooks/", data=data_in)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    result = response.data
    assert "Invalid hash format nada" in str(result["hmac_format"][0])


@pytest.mark.django_db
def test_delete_webhook(
    client: APIClient,
    check_permission_mock: mock.Mock,
    default_user: models.User,
):
    webhook = models.Webhook.objects.create(
        uuid=uuid.uuid4(),
        name="test-webhook-1",
        owner=default_user,
        url="http://www.example.com",
        secret="secret",
    )

    response = client.delete(f"{api_url_v1}/webhooks/{webhook.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.WEBHOOK, Action.DELETE
    )


@pytest.mark.django_db
def test_update_webhook(
    client: APIClient,
    check_permission_mock: mock.Mock,
    default_user: models.User,
):
    webhook = models.Webhook.objects.create(
        uuid=uuid.uuid4(),
        name="test-webhook-1",
        owner=default_user,
        url="http://www.example.com",
        secret="secret",
    )
    new_secret = "gobbledegook"
    response = client.patch(
        f"{api_url_v1}/webhooks/{webhook.id}/",
        data={"test_mode": True, "username": "", "secret": new_secret},
    )
    assert response.status_code == status.HTTP_200_OK

    check_permission_mock.assert_called_once_with(
        mock.ANY, mock.ANY, ResourceType.WEBHOOK, Action.UPDATE
    )
    webhook.refresh_from_db()
    assert webhook.test_mode
    assert webhook.secret.get_secret_value() == new_secret


@pytest.mark.django_db
def test_post_webhook_with_bad_uuid(
    base_client: APIClient,
    check_permission_mock: mock.Mock,
    default_user: models.User,
):
    secret = secrets.token_hex(32)
    signature_header_name = "my-secret-header"
    hmac_signature_prefix = "sha256="
    models.Webhook.objects.create(
        uuid=uuid.uuid4(),
        name="test-webhook-1",
        owner=default_user,
        url="http://www.example.com",
        secret=secret,
        header_key=signature_header_name,
        hmac_signature_prefix=hmac_signature_prefix,
    )
    data = {"a": 1, "b": 2}
    data_bytes = JSONRenderer().render(data)
    hash_object = hmac.new(
        secret.encode("utf-8"), msg=data_bytes, digestmod=hashlib.sha256
    )
    headers = {
        signature_header_name: f"{hmac_signature_prefix}"
        f"{hash_object.hexdigest()}"
    }
    response = base_client.post(
        f"{api_url_v1}/external_webhook/{str(uuid.uuid4())}/post/",
        headers=headers,
        data=data,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_post_webhook_with_form_urlencoded(
    base_client: APIClient,
    check_permission_mock: mock.Mock,
    default_user: models.User,
):
    secret = secrets.token_hex(32)
    signature_header_name = "my-secret-header"
    hmac_signature_prefix = "sha256="
    webhook = models.Webhook.objects.create(
        uuid=uuid.uuid4(),
        name="test-webhook-1",
        owner=default_user,
        url="http://www.example.com",
        secret=secret,
        header_key=signature_header_name,
        hmac_signature_prefix=hmac_signature_prefix,
    )
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
    response = base_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_post_webhook_with_base64_format(
    base_client: APIClient,
    check_permission_mock: mock.Mock,
    default_user: models.User,
):
    secret = secrets.token_hex(32)
    signature_header_name = "my-secret-header"
    hmac_signature_prefix = "sha256="
    webhook = models.Webhook.objects.create(
        uuid=uuid.uuid4(),
        name="test-webhook-1",
        owner=default_user,
        url="http://www.example.com",
        secret=secret,
        header_key=signature_header_name,
        hmac_signature_prefix=hmac_signature_prefix,
        hmac_format="base64",
    )
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
    response = base_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_post_webhook_with_basic_auth(
    base_client: APIClient,
    check_permission_mock: mock.Mock,
    default_user: models.User,
):
    secret = secrets.token_hex(32)
    username = "fred"
    signature_header_name = "Authorization"
    webhook = models.Webhook.objects.create(
        uuid=uuid.uuid4(),
        name="test-webhook-1",
        owner=default_user,
        url="http://www.example.com",
        secret=secret,
        header_key=signature_header_name,
        auth_type="basic",
        username=username,
    )
    user_pass = f"{username}:{secret}"
    auth_value = f"Basic {base64.b64encode(user_pass.encode()).decode()}"
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()
    headers = {
        signature_header_name: auth_value,
        "Content-Type": content_type,
    }
    response = base_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_post_webhook_with_token(
    base_client: APIClient,
    check_permission_mock: mock.Mock,
    default_user: models.User,
):
    secret = secrets.token_hex(32)
    signature_header_name = "my-secret-header"
    webhook = models.Webhook.objects.create(
        uuid=uuid.uuid4(),
        name="test-webhook-1",
        owner=default_user,
        url="http://www.example.com",
        secret=secret,
        header_key=signature_header_name,
        auth_type="token",
    )
    data = {"a": 1, "b": 2}
    content_type = "application/x-www-form-urlencoded"
    data_bytes = urlencode(data).encode()
    headers = {
        signature_header_name: secret,
        "Content-Type": content_type,
    }
    response = base_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data_bytes,
        content_type=content_type,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_post_webhook_with_test_mode_extra_headers(
    base_client: APIClient,
    check_permission_mock: mock.Mock,
    default_user: models.User,
):
    secret = secrets.token_hex(32)
    signature_header_name = "X-Gitlab-Token"
    webhook = models.Webhook.objects.create(
        uuid=uuid.uuid4(),
        name="test-webhook-1",
        owner=default_user,
        url="http://www.example.com",
        auth_type="token",
        secret=secret,
        header_key=signature_header_name,
        test_mode=True,
        additional_data_headers=[
            "X-Gitlab-Event",
            "X-Gitlab-Event-UUID",
            "X-Gitlab-Webhook-UUID",
        ],
    )
    data = {"a": 1, "b": 2}
    headers = {
        "X-Gitlab-Event-UUID": "c2675c66-7e6e-4fe2-9ac3-288534ef34b9",
        "X-Gitlab-Instance": "https://gitlab.com",
        signature_header_name: secret,
        "X-Gitlab-Webhook-UUID": "b697868f-3b59-4a1f-985d-47f79e2b05ff",
        "X-Gitlab-Event": "Push Hook",
    }

    response = base_client.post(
        f"{api_url_v1}/external_webhook/{webhook.uuid}/post/",
        headers=headers,
        data=data,
    )
    assert response.status_code == status.HTTP_200_OK

    webhook.refresh_from_db()
    test_data = yaml.safe_load(webhook.test_content)
    assert test_data["a"] == 1
    assert test_data["b"] == 2
    assert (
        test_data["X-Gitlab-Event-UUID"]
        == "c2675c66-7e6e-4fe2-9ac3-288534ef34b9"
    )
    assert (
        test_data["X-Gitlab-Webhook-UUID"]
        == "b697868f-3b59-4a1f-985d-47f79e2b05ff"
    )
    assert test_data["X-Gitlab-Event"] == "Push Hook"
    assert test_data["eda_webhook_name"] == "test-webhook-1"
    assert webhook.test_content_type == "application/json"
