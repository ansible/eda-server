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
import json
import time
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.renderers import JSONRenderer
from rest_framework.test import APIClient

from aap_eda.api.views.external_event_stream import ExternalEventStreamViewSet
from aap_eda.core import enums, models
from aap_eda.core.utils.credentials import inputs_to_store
from tests.integration.api.test_event_stream import (
    create_event_stream,
    create_event_stream_credential,
    event_stream_post_url,
    get_default_test_org,
)
from tests.integration.constants import api_url_v1


@pytest.mark.parametrize(
    ("auth_status", "side_effect"),
    [
        (status.HTTP_200_OK, None),
        (status.HTTP_403_FORBIDDEN, jwt.exceptions.PyJWTError("Kaboom")),
    ],
)
@pytest.mark.django_db
def test_post_event_stream_with_oauth2_jwt(
    admin_client: APIClient,
    preseed_credential_types,
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

    obj = create_event_stream_credential(
        admin_client, enums.EventStreamCredentialType.OAUTH2_JWT.value, inputs
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
    content_type = "application/json"
    data_bytes = JSONRenderer().render(data)
    headers = {
        header_key: f"Bearer {access_token}",
        "Content-Type": content_type,
    }
    with patch("aap_eda.api.event_stream_authentication.PyJWKClient"):
        with patch(
            "aap_eda.api.event_stream_authentication.jwt_decode",
            side_effect=side_effect,
        ):
            response = admin_client.post(
                event_stream_post_url(event_stream.uuid),
                headers=headers,
                data=data_bytes,
                content_type=content_type,
            )
    assert response.status_code == auth_status


@pytest.mark.parametrize(
    ("required_claims", "auth_status"),
    [
        ("", status.HTTP_200_OK),
        ('{"iss": "https://idp.example.com"}', status.HTTP_200_OK),
        ("groups:\n  - eda-senders\n", status.HTTP_200_OK),
        ('{"iss": "https://evil.example.com"}', status.HTTP_403_FORBIDDEN),
        ('{"groups": ["admins"]}', status.HTTP_403_FORBIDDEN),
        ('{"tenant": "acme"}', status.HTTP_403_FORBIDDEN),
    ],
)
@pytest.mark.django_db
def test_post_event_stream_with_oauth2_jwt_required_claims(
    admin_client: APIClient,
    preseed_credential_types,
    required_claims,
    auth_status,
):
    header_key = "Authorization"
    inputs = {
        "auth_type": "oauth2-jwt",
        "jwks_url": "https://my_as_server/.well-known/jwks.json",
        "audience": "",
        "required_claims": required_claims,
        "http_header_key": header_key,
    }
    obj = create_event_stream_credential(
        admin_client, enums.EventStreamCredentialType.OAUTH2_JWT.value, inputs
    )
    event_stream = create_event_stream(
        admin_client,
        {
            "name": "test-es-claims",
            "eda_credential_id": obj["id"],
            "event_stream_type": obj["credential_type"]["kind"],
            "organization_id": get_default_test_org().id,
            "test_mode": True,
        },
    )

    decoded_claims = {
        "iss": "https://idp.example.com",
        "groups": ["eda-senders", "ops"],
    }
    content_type = "application/json"
    with patch("aap_eda.api.event_stream_authentication.PyJWKClient"):
        with patch(
            "aap_eda.api.event_stream_authentication.jwt_decode",
            return_value=decoded_claims,
        ):
            response = admin_client.post(
                event_stream_post_url(event_stream.uuid),
                headers={
                    header_key: "Bearer dummy",
                    "Content-Type": content_type,
                },
                data=JSONRenderer().render({"a": 1}),
                content_type=content_type,
            )
    assert response.status_code == auth_status


@pytest.mark.parametrize(
    ("required_claims", "error"),
    [
        ("iss: [unclosed", "Must be in JSON or YAML format"),
        ("- eda-senders", "Must be in object format"),
    ],
)
@pytest.mark.django_db
def test_create_oauth2_jwt_credential_with_invalid_required_claims(
    admin_client: APIClient,
    preseed_credential_types,
    required_claims,
    error,
):
    credential_type = models.CredentialType.objects.get(
        name=enums.EventStreamCredentialType.OAUTH2_JWT
    )
    data_in = {
        "name": "bad-claims",
        "inputs": {
            "auth_type": "oauth2-jwt",
            "jwks_url": "https://my_as_server/.well-known/jwks.json",
            "required_claims": required_claims,
            "http_header_key": "Authorization",
        },
        "credential_type_id": credential_type.id,
        "organization_id": get_default_test_org().id,
    }
    response = admin_client.post(
        f"{api_url_v1}/eda-credentials/", data=data_in
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["inputs.required_claims"] == [error]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, {}),
        ("", {}),
        (
            '{"iss": "https://idp.example.com"}',
            {"iss": "https://idp.example.com"},
        ),
        ("groups:\n  - eda-senders\n", {"groups": ["eda-senders"]}),
    ],
)
def test_parse_required_claims(value, expected):
    assert ExternalEventStreamViewSet._parse_required_claims(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "iss: [unclosed",  # not valid YAML
        "- eda-senders",  # valid YAML but not a mapping
        "just a string",
    ],
)
def test_parse_required_claims_invalid_fails_closed(value):
    with pytest.raises(
        AuthenticationFailed, match="Invalid required claims configuration"
    ):
        ExternalEventStreamViewSet._parse_required_claims(value)


@pytest.mark.django_db
def test_post_event_stream_with_corrupt_stored_required_claims(
    admin_client: APIClient,
    preseed_credential_types,
):
    """A stored value that bypassed save-time validation must reject."""
    header_key = "Authorization"
    inputs = {
        "auth_type": "oauth2-jwt",
        "jwks_url": "https://my_as_server/.well-known/jwks.json",
        "audience": "",
        "required_claims": '{"iss": "https://idp.example.com"}',
        "http_header_key": header_key,
    }
    obj = create_event_stream_credential(
        admin_client, enums.EventStreamCredentialType.OAUTH2_JWT.value, inputs
    )
    event_stream = create_event_stream(
        admin_client,
        {
            "name": "test-es-corrupt-claims",
            "eda_credential_id": obj["id"],
            "event_stream_type": obj["credential_type"]["kind"],
            "organization_id": get_default_test_org().id,
            "test_mode": True,
        },
    )

    # Bypass API validation to emulate a corrupt stored value
    credential = models.EdaCredential.objects.get(pk=obj["id"])
    credential.inputs = inputs_to_store(
        {**inputs, "required_claims": "- not-a-mapping"}
    )
    credential.save(update_fields=["inputs"])

    content_type = "application/json"
    with patch("aap_eda.api.event_stream_authentication.PyJWKClient"):
        with patch(
            "aap_eda.api.event_stream_authentication.jwt_decode",
            return_value={"iss": "https://idp.example.com"},
        ) as mock_decode:
            response = admin_client.post(
                event_stream_post_url(event_stream.uuid),
                headers={
                    header_key: "Bearer dummy",
                    "Content-Type": content_type,
                },
                data=JSONRenderer().render({"a": 1}),
                content_type=content_type,
            )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    mock_decode.assert_not_called()
    event_stream.refresh_from_db()
    assert event_stream.events_received == 1
    assert "Invalid required claims configuration" in (
        event_stream.test_error_message
    )


@pytest.mark.parametrize(
    ("token_signer", "auth_status"),
    [
        ("trusted", status.HTTP_200_OK),
        ("untrusted", status.HTTP_403_FORBIDDEN),
    ],
)
@pytest.mark.django_db
def test_post_event_stream_legacy_credential_with_signed_jwt(
    admin_client: APIClient,
    preseed_credential_types,
    token_signer,
    auth_status,
):
    """Credentials saved before required_claims existed keep working.

    Their stored inputs have no required_claims key at all. A real RS256
    token is verified against a JWKS; only the JWKS fetch is stubbed.
    """
    header_key = "Authorization"
    inputs = {
        "auth_type": "oauth2-jwt",
        "jwks_url": "https://my_as_server/.well-known/jwks.json",
        "audience": "eda",
        "http_header_key": header_key,
    }
    obj = create_event_stream_credential(
        admin_client, enums.EventStreamCredentialType.OAUTH2_JWT.value, inputs
    )
    event_stream = create_event_stream(
        admin_client,
        {
            "name": "test-es-legacy",
            "eda_credential_id": obj["id"],
            "event_stream_type": obj["credential_type"]["kind"],
            "organization_id": get_default_test_org().id,
            "test_mode": True,
        },
    )

    # Rewrite stored inputs exactly as a pre-upgrade install has them
    credential = models.EdaCredential.objects.get(pk=obj["id"])
    credential.inputs = inputs_to_store(inputs)
    credential.save(update_fields=["inputs"])
    credential.refresh_from_db()
    assert "required_claims" not in credential.inputs.get_secret_value()

    trusted_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048
    )
    jwk = json.loads(
        jwt.algorithms.RSAAlgorithm.to_jwk(trusted_key.public_key())
    )
    jwk.update({"kid": "k1", "use": "sig", "alg": "RS256"})
    signer = (
        trusted_key
        if token_signer == "trusted"
        else rsa.generate_private_key(public_exponent=65537, key_size=2048)
    )
    now = int(time.time())
    token = jwt.encode(
        {"iss": "https://idp.example.com", "aud": "eda", "exp": now + 300},
        signer,
        algorithm="RS256",
        headers={"kid": "k1"},
    )

    content_type = "application/json"
    with patch.object(
        jwt.PyJWKClient, "fetch_data", return_value={"keys": [jwk]}
    ):
        response = admin_client.post(
            event_stream_post_url(event_stream.uuid),
            headers={
                header_key: f"Bearer {token}",
                "Content-Type": content_type,
            },
            data=JSONRenderer().render({"a": 1}),
            content_type=content_type,
        )
    assert response.status_code == auth_status
