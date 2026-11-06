"""Run awx core plugins."""

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

import logging

from awx_plugins.credentials.aim import aim_plugin
from awx_plugins.credentials.aws_secretsmanager import aws_secretmanager_plugin
from awx_plugins.credentials.azure_kv import azure_keyvault_plugin
from awx_plugins.credentials.centrify_vault import centrify_plugin
from awx_plugins.credentials.conjur import conjur_plugin
from awx_plugins.credentials.dsv import dsv_plugin
from awx_plugins.credentials.github_app import github_app_lookup
from awx_plugins.credentials.hashivault import (
    hashivault_kv_plugin,
    hashivault_ssh_plugin,
)
from awx_plugins.credentials.tss import tss_plugin

from aap_eda.core.exceptions import (
    CredentialPluginError,
    UnknownPluginTypeError,
)

LOGGER = logging.getLogger(__name__)

PLUGIN_TYPES = {
    "aim": aim_plugin,
    "aws_secretsmanager_credential": aws_secretmanager_plugin,
    "azure_kv": azure_keyvault_plugin,
    "centrify_vault_kv": centrify_plugin,
    "conjur": conjur_plugin,
    "github_app": github_app_lookup,
    "hashivault_kv": hashivault_kv_plugin,
    "hashivault_ssh": hashivault_ssh_plugin,
    "thycotic_dsv": dsv_plugin,
    "thycotic_tss": tss_plugin,
}


def run_plugin(plugin_type: str, inputs: dict, metadata: dict) -> dict:
    """Execute the external SMS plugins."""
    if plugin_type in PLUGIN_TYPES:
        try:
            return PLUGIN_TYPES[plugin_type].backend(**inputs, **metadata)
        except Exception as err:
            msg = (
                f"Error executing credential plugin {plugin_type}: {str(err)}"
            )
            LOGGER.error(msg)
            raise CredentialPluginError(msg) from err

    raise UnknownPluginTypeError(
        f"Unknown plugin type {plugin_type} passed in"
    )
