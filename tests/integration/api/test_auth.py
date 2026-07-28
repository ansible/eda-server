#  Copyright 2023 Red Hat, Inc.
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

import pytest
from rest_framework import status
from rest_framework.test import APIClient, RequestsClient

from aap_eda.core import models
from aap_eda.services.auth import jwt_refresh_token
from tests.integration.constants import api_url_v1

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


auth_url = f"https://testserver{api_url_v1}/auth/session"
login_url = f"{auth_url}/login/"
logout_url = f"{auth_url}/logout/"


@pytest.fixture(scope="module")
def live_server(live_server):
    return live_server


def test_session_login_logout(live_server, default_user: models.User):
    client = RequestsClient()
    response = client.get(login_url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    csrf_token = response.cookies["csrftoken"]

    response = client.post(
        login_url,
        headers={
            "X-CSRFToken": csrf_token,
        },
        json={
            "username": "luke.skywalker",
            "password": "secret",
        },
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.text == ""
    assert "sessionid" in response.cookies
    csrf_token = response.cookies["csrftoken"]

    response = client.post(
        logout_url,
        headers={
            "X-CSRFToken": csrf_token,
        },
    )
    assert response.text == ""
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_session_login_invalid_credentials(
    base_client: APIClient, default_user: models.User
):
    response = base_client.post(
        login_url,
        data={
            "username": "luke.skywalker",
            "password": "invalid",
        },
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {
        "detail": "Invalid credentials or user is disabled."
    }


@pytest.mark.django_db
def test_logout_unauthenticated(base_client: APIClient):
    response = base_client.post(logout_url)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


def _get_crsf_token(client: RequestsClient):
    response = client.get(login_url)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    return response.cookies["csrftoken"]


@pytest.mark.django_db
def test_refresh_token(base_client: RequestsClient):
    user, _ = models.User.objects.get_or_create(
        username="_token_service_user",
        is_service_account=True,
    )
    data = {"refresh": jwt_refresh_token(user.id)}
    url = f"https://testserver{api_url_v1}/auth/token/refresh/"
    response = base_client.post(url, data)
    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data


@pytest.mark.django_db
def test_refresh_token_with_bad_token(base_client: RequestsClient):
    data = {"refresh": "bad token"}
    url = f"https://testserver{api_url_v1}/auth/token/refresh/"
    response = base_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_refresh_token_preserves_activation_instance_id(
    base_client: RequestsClient,
):
    """Test that refresh token preserves activation_instance_id in new
    access token.
    """
    from aap_eda.services.auth import create_jwt_token, parse_jwt_token

    activation_id = "123"
    _, refresh_token = create_jwt_token(activation_instance_id=activation_id)

    data = {"refresh": refresh_token}
    url = f"https://testserver{api_url_v1}/auth/token/refresh/"
    response = base_client.post(url, data)

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data

    # Parse new access token and verify activation_instance_id is preserved
    new_access_token = response.data["access"]
    payload = parse_jwt_token(new_access_token)

    assert payload["activation_instance_id"] == activation_id
    assert payload["token_type"] == "access"


@pytest.mark.django_db
def test_refresh_token_preserves_activation_instance_id_uuid(
    base_client: RequestsClient,
):
    """Test that refresh token preserves UUID activation_instance_id."""
    from aap_eda.services.auth import create_jwt_token, parse_jwt_token

    activation_id = "550e8400-e29b-41d4-a716-446655440000"
    _, refresh_token = create_jwt_token(activation_instance_id=activation_id)

    data = {"refresh": refresh_token}
    url = f"https://testserver{api_url_v1}/auth/token/refresh/"
    response = base_client.post(url, data)

    assert response.status_code == status.HTTP_200_OK

    # Verify UUID is preserved
    new_access_token = response.data["access"]
    payload = parse_jwt_token(new_access_token)

    assert payload["activation_instance_id"] == activation_id


@pytest.mark.django_db
def test_refresh_token_without_activation_instance_id_legacy(
    base_client: RequestsClient,
):
    """Test that legacy refresh token without activation_instance_id
    creates legacy access token.
    """
    from aap_eda.services.auth import create_jwt_token, parse_jwt_token

    # Create legacy token without activation_instance_id
    _, refresh_token = create_jwt_token()

    data = {"refresh": refresh_token}
    url = f"https://testserver{api_url_v1}/auth/token/refresh/"
    response = base_client.post(url, data)

    assert response.status_code == status.HTTP_200_OK

    # Verify new access token also has no activation_instance_id
    new_access_token = response.data["access"]
    payload = parse_jwt_token(new_access_token)

    assert "activation_instance_id" not in payload
    assert payload["token_type"] == "access"
