"""Test the credential plugin."""
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

from unittest import mock

import pytest
from awx_plugins.credentials.plugin import CredentialPlugin

from aap_eda.core.exceptions import UnknownPluginType
from aap_eda.core.utils.credential_plugins import run_plugin


@pytest.mark.parametrize(
    ("plugin_type"),
    [
        "aim",
        "aws_secretsmanager_credential",
        "azure_kv",
        "centrify_vault_kv",
        "conjur",
        "github_app",
        "hashivault_kv",
        "hashivault_ssh",
        "thycotic_dsv",
        "thycotic_tss",
    ],
)
def test_run_plugin(plugin_type):
    """Test run a single plugin backend."""
    with mock.patch.object(CredentialPlugin, "backend") as mock_backend:
        mock_backend.return_value = "abc"
        run_plugin(plugin_type, {}, {})


def test_unknown_plugin_type():
    """Test run a missing plugin."""
    with pytest.raises(UnknownPluginType):
        run_plugin("dummy", {}, {})
