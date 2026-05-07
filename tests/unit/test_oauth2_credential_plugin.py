"""Tests for the OAuth2 Client Credentials credential plugin in EDA."""
#  Copyright 2026 Red Hat, Inc.
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

from unittest import mock

import pytest
import responses
from awx_plugins.credentials.plugin import CredentialPlugin

from aap_eda.core.enums import DefaultCredentialType
from aap_eda.core.utils.credential_plugins import (
    PLUGIN_TYPES,
    run_plugin,
)


TOKEN_URL = (
    "https://login.microsoftonline.com/"
    "00000000-0000-0000-0000-000000000000/oauth2/v2.0/token"
)
CLIENT_ID = "11111111-1111-1111-1111-111111111111"
CLIENT_SECRET = "test-secret-value"
FAKE_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.fake.token"


class TestOAuth2PluginRegistration:
    """Verify the plugin is wired into the EDA plugin registry."""

    def test_plugin_key_in_plugin_types(self):
        assert "oauth2_client_credentials" in PLUGIN_TYPES

    def test_plugin_is_credential_plugin_instance(self):
        plugin = PLUGIN_TYPES["oauth2_client_credentials"]
        assert isinstance(plugin, CredentialPlugin)

    def test_plugin_name_matches_enum(self):
        plugin = PLUGIN_TYPES["oauth2_client_credentials"]
        assert (
            plugin.name
            == DefaultCredentialType.OAUTH2_CLIENT_CREDENTIALS
        )

    def test_plugin_backend_is_callable(self):
        plugin = PLUGIN_TYPES["oauth2_client_credentials"]
        assert callable(plugin.backend)


class TestOAuth2RunPlugin:
    """Verify the run_plugin dispatcher routes correctly."""

    def test_run_plugin_calls_backend(self):
        with mock.patch.object(
            CredentialPlugin, "backend"
        ) as mock_backend:
            mock_backend.return_value = "token-value"
            result = run_plugin(
                "oauth2_client_credentials", {}, {}
            )
            assert result == "token-value"

    @responses.activate
    def test_run_plugin_real_backend_success(self):
        responses.post(
            TOKEN_URL,
            json={
                "access_token": FAKE_TOKEN,
                "token_type": "Bearer",
                "expires_in": 3600,
            },
            status=200,
        )

        result = run_plugin(
            "oauth2_client_credentials",
            {
                "token_url": TOKEN_URL,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
            {"scope": ""},
        )

        assert result == FAKE_TOKEN

    @responses.activate
    def test_run_plugin_real_backend_with_scope(self):
        ado_scope = (
            "499b84ac-1321-427f-aa17-267ca6975798/.default"
        )
        responses.post(
            TOKEN_URL,
            json={
                "access_token": FAKE_TOKEN,
                "token_type": "Bearer",
                "expires_in": 3600,
            },
            status=200,
        )

        result = run_plugin(
            "oauth2_client_credentials",
            {
                "token_url": TOKEN_URL,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
            {"scope": ado_scope},
        )

        assert result == FAKE_TOKEN
        request_body = responses.calls[0].request.body
        assert "499b84ac" in request_body

    @responses.activate
    def test_run_plugin_real_backend_failure(self):
        responses.post(
            TOKEN_URL,
            json={
                "error": "invalid_client",
                "error_description": "Bad credentials.",
            },
            status=401,
        )

        from aap_eda.core.exceptions import CredentialPluginError

        with pytest.raises(CredentialPluginError):
            run_plugin(
                "oauth2_client_credentials",
                {
                    "token_url": TOKEN_URL,
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                },
                {},
            )
