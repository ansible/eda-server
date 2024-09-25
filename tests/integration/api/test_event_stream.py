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
import hmac
import secrets
from typing import List

import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework import status
from rest_framework.renderers import JSONRenderer
from rest_framework.test import APIClient

from aap_eda.core import enums, models
from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_list_event_streams(
    admin_client: APIClient,
    default_event_streams: List[models.EventStream],
    default_vault_credential,
):
    response = admin_client.get(f"{api_url_v1}/event-streams/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 2
    assert response.data["results"][0]["name"] == default_event_streams[0].name
    assert response.data["results"][0]["owner"] == "luke.skywalker"


@pytest.mark.django_db
def test_retrieve_event_stream(
    admin_client: APIClient,
    default_event_streams: List[models.EventStream],
    default_vault_credential,
):
    event_stream = default_event_streams[0]
    response = admin_client.get(
        f"{api_url_v1}/event-streams/{event_stream.id}/"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == default_event_streams[0].name
    assert response.data["url"] == default_event_streams[0].url
    assert response.data["owner"] == "luke.skywalker"


@pytest.mark.django_db
def test_create_event_stream(
    admin_client: APIClient,
    default_hmac_credential: models.EdaCredential,
    default_organization: models.Organization,
):
    data_in = {
        "name": "test_event_stream",
        "eda_credential_id": default_hmac_credential.id,
        "organization_id": default_organization.id,
    }
    event_stream = create_event_stream(admin_client, data_in)
    assert event_stream.name == "test_event_stream"
    assert event_stream.owner.username == "test.admin"


@pytest.mark.django_db
def test_create_event_stream_without_credentials(
    admin_client: APIClient, default_organization: models.Organization
):
    data_in = {
        "name": "test_es",
        "organization_id": default_organization.id,
    }
    response = admin_client.post(f"{api_url_v1}/event-streams/", data=data_in)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "eda_credential_id": ["This field is required."],
    }


@pytest.mark.django_db
def test_delete_event_stream(
    admin_client: APIClient,
    default_event_stream: models.EventStream,
):
    response = admin_client.delete(
        f"{api_url_v1}/event-streams/{default_event_stream.id}/"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_delete_event_stream_with_exception(
    admin_client: APIClient,
    default_activation: models.Activation,
    default_event_stream: models.EventStream,
):
    activation = default_activation
    activation.event_streams.add(default_event_stream)

    response = admin_client.delete(
        f"{api_url_v1}/event-streams/{default_event_stream.id}/"
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        f"Event stream '{default_event_stream.name}' is being referenced by "
        "1 activation(s) and cannot be deleted"
    ) in response.data["detail"]


@pytest.mark.django_db
def test_post_event_stream_with_bad_uuid(
    admin_client: APIClient,
    default_event_stream: models.EventStream,
):
    data = {"a": 1, "b": 2}
    response = admin_client.post(
        event_stream_post_url("gobble-de-gook"),
        data=data,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_fetching_event_stream_credential(
    admin_client: APIClient,
    preseed_credential_types,
):
    secret = secrets.token_hex(32)
    inputs = {
        "auth_type": "token",
        "token": secret,
        "http_header_key": "Authorization",
    }
    create_event_stream_credential(
        admin_client,
        enums.EventStreamCredentialType.TOKEN.value,
        inputs,
        "demo1",
    )

    inputs = {
        "auth_type": "basic",
        "password": secret,
        "username": "fred",
        "http_header_key": "Authorization",
    }
    create_event_stream_credential(
        admin_client,
        enums.EventStreamCredentialType.BASIC.value,
        inputs,
        "demo2",
    )
    response = admin_client.get(
        f"{api_url_v1}/eda-credentials/?credential_type__kind=token"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["results"][0]["name"] == "demo1"


@pytest.mark.parametrize(
    ("inputs", "cred_type", "settings_key", "error_msg"),
    [
        (
            {
                "auth_type": "basic",
                "username": "fred",
                "password": secrets.token_hex(32),
                "http_header_key": "Authorization",
            },
            enums.EventStreamCredentialType.BASIC.value,
            "EVENT_STREAM_BASE_URL",
            (
                "EventStream of type Basic Event Stream cannot be used "
                "because EVENT_STREAM_BASE_URL is not configured. "
                "Please check with your site administrator."
            ),
        ),
    ],
)
@pytest.mark.django_db
def test_post_event_stream_with_missing_settings(
    admin_client: APIClient,
    preseed_credential_types,
    inputs,
    cred_type,
    settings_key,
    error_msg,
):
    obj = create_event_stream_credential(admin_client, cred_type, inputs)

    data_in = {
        "name": "test-es-1",
        "eda_credential_id": obj["id"],
        "test_mode": True,
        "organization_id": get_default_test_org().id,
    }
    with override_settings(settings_key=None):
        response = admin_client.post(
            f"{api_url_v1}/event-streams/", data=data_in
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {"eda_credential_id": [error_msg]}


def create_event_stream_credential(
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
        "organization_id": get_default_test_org().id,
    }
    response = client.post(f"{api_url_v1}/eda-credentials/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


def create_event_stream(
    client: APIClient, data_in: dict
) -> models.EventStream:
    with override_settings(
        EVENT_STREAM_BASE_URL="https://www.example.com/",
        EVENT_STREAM_MTLS_BASE_URL="https://www.example.com/",
    ):
        response = client.post(f"{api_url_v1}/event-streams/", data=data_in)
        assert response.status_code == status.HTTP_201_CREATED
        return models.EventStream.objects.get(id=response.data["id"])


def event_stream_post_url(event_stream_uuid: str) -> str:
    return f"{api_url_v1}/external_event_stream/{event_stream_uuid}/post/"


def hash_digest(data: dict, secret: str, digestmod) -> str:
    data_bytes = JSONRenderer().render(data)
    hash_object = hmac.new(
        secret.encode("utf-8"), msg=data_bytes, digestmod=digestmod
    )
    return hash_object.hexdigest()


def get_default_test_org() -> models.Organization:
    return models.Organization.objects.get_or_create(
        name=settings.DEFAULT_ORGANIZATION_NAME,
        description="The default organization",
    )[0]
