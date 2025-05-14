"""Fetch external secrets."""
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

import yaml

from aap_eda.core import models
from aap_eda.core.exceptions import CredentialPluginError
from aap_eda.core.utils.credential_plugins import run_plugin

LOGGER = logging.getLogger(__name__)


def get_external_secrets(credential_id: int) -> dict:
    """Fetch secrets from an external SMS."""
    result = {}
    for obj in models.CredentialInputSource.objects.filter(
        target_credential=credential_id
    ):
        try:
            inputs = obj.source_credential.inputs.get_secret_value()
            metadata = obj.metadata.get_secret_value()

            value = run_plugin(
                obj.source_credential.credential_type.namespace,
                yaml.safe_load(inputs),
                yaml.safe_load(metadata),
            )
            result[obj.input_field_name] = value
        except CredentialPluginError as err:
            msg = (
                f"Error fetching field: {obj.input_field_name} "
                f"defined in: {obj.target_credential.name} using the external "
                f"credentials defined in: {obj.source_credential.name} "
                f"Error: {str(err)}"
            )
            LOGGER.error(msg)
            raise CredentialPluginError(msg) from err
    return result
