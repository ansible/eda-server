#  Copyright 2025 Red Hat, Inc.
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

"""
Tests for the full settings bootstrap path.

Includes RESOURCE_SERVER__URL logic and authentication class configuration.
"""

import pytest
from dynaconf import Dynaconf

from aap_eda.settings import core, defaults
from aap_eda.settings.post_load import apply_resource_server_auth, post_loading


@pytest.fixture
def mock_settings():
    """Create a mock settings object similar to the bootstrap path."""
    # Create a fresh Dynaconf instance for each test to avoid state pollution
    mock_settings = Dynaconf(
        settings_files=[defaults.__file__, core.__file__],
        fresh=True,  # Force a fresh load of settings
    )
    mock_settings.SECRET_KEY = "secret"
    return mock_settings


def test_resource_server_without_websocket_worker(mock_settings):
    """
    Test RESOURCE_SERVER__URL sets mixed JWT auth for non-websocket workers.
    """
    # Simulate the bootstrap path in default.py
    mock_settings.RESOURCE_SERVER__URL = "https://localhost"
    mock_settings.WORKER_KIND = "api"
    post_loading(mock_settings)
    apply_resource_server_auth(mock_settings)

    # Verify that both authentication classes are present
    assert mock_settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == [
        "ansible_base.jwt_consumer.eda.auth.EDAJWTAuthentication",
        "aap_eda.api.authentication.WebsocketJWTAuthentication",
    ]


def test_resource_server_with_websocket_worker(mock_settings):
    """Test that RESOURCE_SERVER__URL does not override websocket-only auth."""
    # Simulate the bootstrap path in default.py
    mock_settings.RESOURCE_SERVER__URL = "https://localhost"
    mock_settings.WORKER_KIND = "websocket"
    post_loading(mock_settings)
    apply_resource_server_auth(mock_settings)

    # Verify that the websocket-only auth is preserved
    assert mock_settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == [
        "aap_eda.api.authentication.WebsocketJWTAuthentication",
    ]


def test_no_resource_server_with_websocket_worker(mock_settings):
    """Test websocket worker without RESOURCE_SERVER__URL."""
    # Explicitly clear RESOURCE_SERVER__URL
    # (defaults.py sets it to "https://localhost")
    mock_settings.RESOURCE_SERVER__URL = None
    mock_settings.WORKER_KIND = "websocket"
    post_loading(mock_settings)
    apply_resource_server_auth(mock_settings)

    # Verify websocket-only authentication
    assert mock_settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == [
        "aap_eda.api.authentication.WebsocketJWTAuthentication",
    ]


def test_no_resource_server_without_websocket_worker(mock_settings):
    """Test non-websocket worker without RESOURCE_SERVER__URL."""
    # Explicitly clear RESOURCE_SERVER__URL
    # (defaults.py sets it to "https://localhost")
    mock_settings.RESOURCE_SERVER__URL = None
    mock_settings.WORKER_KIND = "api"
    post_loading(mock_settings)
    apply_resource_server_auth(mock_settings)

    # Should have the exact default authentication classes from core.py
    # Order matters for DRF authentication - tried in sequence
    assert mock_settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == [
        "aap_eda.api.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
        "ansible_base.jwt_consumer.eda.auth.EDAJWTAuthentication",
    ]


@pytest.mark.parametrize(
    "resource_server_url,worker_kind,expected_auth",
    [
        # Non-websocket worker with resource server
        (
            "https://localhost",
            "api",
            [
                "ansible_base.jwt_consumer.eda.auth.EDAJWTAuthentication",
                "aap_eda.api.authentication.WebsocketJWTAuthentication",
            ],
        ),
        # Non-websocket worker without resource server - gets default auth
        (
            None,
            "api",
            [
                "aap_eda.api.authentication.SessionAuthentication",
                "rest_framework.authentication.BasicAuthentication",
                "ansible_base.jwt_consumer.eda.auth.EDAJWTAuthentication",
            ],
        ),
        # Websocket worker with resource server - preserves websocket-only
        (
            "https://localhost",
            "websocket",
            ["aap_eda.api.authentication.WebsocketJWTAuthentication"],
        ),
        # Websocket worker without resource server
        (
            None,
            "websocket",
            ["aap_eda.api.authentication.WebsocketJWTAuthentication"],
        ),
        # Case-insensitive: "WebSocket" should work
        (
            "https://localhost",
            "WebSocket",
            ["aap_eda.api.authentication.WebsocketJWTAuthentication"],
        ),
        # Case-insensitive: "WEBSOCKET" should work
        (
            "https://localhost",
            "WEBSOCKET",
            ["aap_eda.api.authentication.WebsocketJWTAuthentication"],
        ),
        # Other worker kinds should get mixed auth with resource server
        (
            "https://localhost",
            "activation",
            [
                "ansible_base.jwt_consumer.eda.auth.EDAJWTAuthentication",
                "aap_eda.api.authentication.WebsocketJWTAuthentication",
            ],
        ),
    ],
)
def test_authentication_class_combinations(
    mock_settings, resource_server_url, worker_kind, expected_auth
):
    """Parameterized test for different combinations of settings."""
    # Set or clear RESOURCE_SERVER__URL
    # (defaults.py sets it to "https://localhost")
    mock_settings.RESOURCE_SERVER__URL = resource_server_url
    mock_settings.WORKER_KIND = worker_kind
    post_loading(mock_settings)
    apply_resource_server_auth(mock_settings)

    assert (
        mock_settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
        == expected_auth
    )
