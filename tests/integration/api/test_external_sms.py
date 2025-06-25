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
from rest_framework.test import APIClient

from aap_eda.core import models
from aap_eda.core.exceptions import CredentialPluginError
from aap_eda.core.utils.external_sms import get_external_secrets


@pytest.mark.parametrize(
    (
        "value",
        "exception",
        "exception_message",
    ),
    [
        (
            "baz",
            None,
            None,
        ),
        (
            None,
            CredentialPluginError,
            (
                "Error fetching field: password defined in: "
                "sample-reg-credential "
                "using the external credentials defined in: "
                "sample-hashi-credential "
                "Error: kaboom"
            ),
        ),
    ],
)
@pytest.mark.django_db
def test_fetch_external_sms(
    admin_client: APIClient,
    default_organization: models.Organization,
    preseed_credential_types,
    default_credential_input_source: models.CredentialInputSource,
    value,
    exception,
    exception_message,
):
    target_id = default_credential_input_source.target_credential.id
    if value:
        with mock.patch(
            "aap_eda.core.utils.external_sms.run_plugin", return_value=value
        ):
            assert value == get_external_secrets(target_id)["password"]

    if exception:
        with pytest.raises(exception) as excinfo:
            with mock.patch(
                "aap_eda.core.utils.external_sms.run_plugin",
                side_effect=CredentialPluginError("kaboom"),
            ):
                get_external_secrets(target_id)

        assert exception_message in str(excinfo.value)
