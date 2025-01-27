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
from typing import List

import pytest

from aap_eda.core import enums, models
from aap_eda.core.utils.credentials import inputs_to_store


@pytest.fixture
def aap_credentials(
    default_organization: models.Organization,
    preseed_credential_types,
) -> List[models.EdaCredential]:
    """Return two RH AAP Credentials"""
    aap_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.AAP
    )

    data = "secret"

    return models.EdaCredential.objects.bulk_create(
        [
            models.EdaCredential(
                name="aap-credential-1",
                description="First RH-AAP Credential",
                inputs=inputs_to_store(
                    {
                        "host": "https://first_eda_controller_url",
                        "ssl_verify": "no",
                        "oauth_token": "token",
                    }
                ),
                credential_type=aap_credential_type,
                organization=default_organization,
            ),
            models.EdaCredential(
                name="aap-credential-2",
                description="Second RH-AAP Credential",
                inputs=inputs_to_store(
                    {
                        "host": "https://second_eda_controller_url",
                        "username": "adam",
                        "password": data,
                        "ssl_verify": "no",
                        "oauth_token": "",
                    }
                ),
                credential_type=aap_credential_type,
                organization=default_organization,
            ),
        ]
    )


@pytest.fixture
def analytics_settings():
    """Mock application settings with proper attribute access."""

    class Settings:
        INSIGHTS_TRACKING_STATE = True
        AUTOMATION_ANALYTICS_LAST_GATHER = None
        AUTOMATION_ANALYTICS_LAST_ENTRIES = '{"key": "value"}'
        AUTOMATION_ANALYTICS_URL = "https://url"
        REDHAT_USERNAME = "dummy"
        REDHAT_PASSWORD = "dummy"

    return Settings()
