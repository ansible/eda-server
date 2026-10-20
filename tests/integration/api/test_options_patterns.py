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
"""Integration tests verifying that OPTIONS metadata exposes
CleanTextMixin ``pattern`` / ``patternDescription`` on eligible
text fields for every standard CRUD action that uses a
CleanTextMixin-bearing serializer.

These tests cover the fix in ``EDAMetadata.determine_actions``
(setting ``view.action`` per HTTP method) and the new
``get_serializer_class`` overrides on viewsets that previously
used a static ``serializer_class``.

Validation is gated behind ``ENHANCED_INPUT_VALIDATION_ENABLED``,
so a module-level autouse fixture enables it for every test.
"""

from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.constants import api_url_v1


@pytest.fixture(autouse=True)
def enable_input_validation(settings):
    settings.ENHANCED_INPUT_VALIDATION_ENABLED = True
    settings.RULEBOOK_WORKER_QUEUES = []


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
def _get_options_actions(client, url):
    """Return the ``actions`` dict from an OPTIONS response."""
    response = client.options(url)
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"OPTIONS {url} returned {response.status_code}"
    return response.data.get("actions", {})


def _assert_pattern_on_field(actions, method, field_name, url=""):
    """Assert that *field_name* under *method* carries pattern keys."""
    method_fields = actions.get(method, {})
    assert method_fields, (
        f"No {method} action in OPTIONS for {url}; "
        f"available: {list(actions.keys())}"
    )
    field_info = method_fields.get(field_name, {})
    assert field_info, (
        f"Field '{field_name}' not in {method} action for {url}; "
        f"available: {list(method_fields.keys())}"
    )
    assert (
        "pattern" in field_info
    ), f"Missing 'pattern' on {field_name} in {method} for {url}"
    assert "patternDescription" in field_info, (
        f"Missing 'patternDescription' on {field_name} "
        f"in {method} for {url}"
    )


def _assert_no_pattern_on_field(actions, method, field_name):
    """Assert that *field_name* under *method* does NOT carry patterns."""
    method_fields = actions.get(method, {})
    if not method_fields:
        return
    field_info = method_fields.get(field_name, {})
    if not field_info:
        return
    assert "pattern" not in field_info


# ---------------------------------------------------------------
# List (collection) endpoints — POST
# ---------------------------------------------------------------
@pytest.mark.django_db
class TestOptionsPostPatterns:
    """OPTIONS on collection endpoints must expose patterns in POST."""

    def test_teams_post(
        self,
        use_local_resource_setting,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/teams/"
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "POST", "name", url)

    def test_event_streams_post(
        self,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/event-streams/"
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "POST", "name", url)

    def test_decision_environments_post(
        self,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/decision-environments/"
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "POST", "name", url)

    def test_users_post(
        self,
        use_local_resource_setting,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/users/"
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "POST", "username", url)

    def test_awx_tokens_post(
        self,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/users/me/awx-tokens/"
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "POST", "name", url)

    def test_credential_input_sources_post(
        self,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/credential-input-sources/"
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "POST", "description", url)

    def test_eda_credentials_post(
        self,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/eda-credentials/"
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "POST", "name", url)

    def test_projects_post(
        self,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/projects/"
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "POST", "name", url)

    def test_credential_types_post(
        self,
        superuser_client: APIClient,
    ):
        url = f"{api_url_v1}/credential-types/"
        actions = _get_options_actions(superuser_client, url)
        _assert_pattern_on_field(actions, "POST", "name", url)

    @patch(
        "aap_eda.api.views.activation.check_dispatcherd_workers_health",
        return_value=True,
    )
    def test_activations_post(
        self,
        mock_health_check,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/activations/"
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "POST", "name", url)

    def test_organizations_post(
        self,
        use_local_resource_setting,
        superuser_client: APIClient,
    ):
        url = f"{api_url_v1}/organizations/"
        actions = _get_options_actions(superuser_client, url)
        _assert_pattern_on_field(actions, "POST", "name", url)


# ---------------------------------------------------------------
# Detail endpoints — PATCH
# ---------------------------------------------------------------
@pytest.mark.django_db
class TestOptionsPatchPatterns:
    """OPTIONS on detail endpoints must expose patterns in PATCH."""

    def test_teams_patch(
        self,
        use_local_resource_setting,
        default_team: models.Team,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/teams/{default_team.id}/"
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "PATCH", "name", url)

    def test_decision_environments_patch(
        self,
        default_decision_environment: models.DecisionEnvironment,
        admin_client: APIClient,
    ):
        url = (
            f"{api_url_v1}/decision-environments/"
            f"{default_decision_environment.id}/"
        )
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "PATCH", "name", url)

    def test_event_streams_patch(
        self,
        default_event_stream: models.EventStream,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/event-streams/" f"{default_event_stream.id}/"
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "PATCH", "name", url)

    def test_users_patch(
        self,
        use_local_resource_setting,
        admin_user: models.User,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/users/{admin_user.id}/"
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "PATCH", "username", url)

    @patch(
        "aap_eda.api.views.activation.check_dispatcherd_workers_health",
        return_value=True,
    )
    def test_activations_patch(
        self,
        mock_health_check,
        admin_awx_token: models.AwxToken,
        activation_payload: dict,
        admin_client: APIClient,
    ):
        activation_payload["is_enabled"] = False
        response = admin_client.post(
            f"{api_url_v1}/activations/",
            data=activation_payload,
        )
        assert response.status_code == status.HTTP_201_CREATED
        activation_id = response.data["id"]
        url = f"{api_url_v1}/activations/{activation_id}/"
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "PATCH", "name", url)

    def test_credential_types_patch(
        self,
        credential_type: models.CredentialType,
        superuser_client: APIClient,
    ):
        url = f"{api_url_v1}/credential-types/" f"{credential_type.id}/"
        actions = _get_options_actions(superuser_client, url)
        _assert_pattern_on_field(actions, "PATCH", "name", url)

    def test_eda_credentials_patch(
        self,
        default_registry_credential: models.EdaCredential,
        admin_client: APIClient,
    ):
        url = (
            f"{api_url_v1}/eda-credentials/"
            f"{default_registry_credential.id}/"
        )
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "PATCH", "name", url)

    def test_credential_input_sources_patch(
        self,
        default_credential_input_source: models.CredentialInputSource,
        admin_client: APIClient,
    ):
        url = (
            f"{api_url_v1}/credential-input-sources/"
            f"{default_credential_input_source.id}/"
        )
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "PATCH", "description", url)

    def test_projects_patch(
        self,
        default_project: models.Project,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/projects/{default_project.id}/"
        actions = _get_options_actions(admin_client, url)
        _assert_pattern_on_field(actions, "PATCH", "name", url)

    def test_organizations_patch(
        self,
        use_local_resource_setting,
        new_organization: models.Organization,
        superuser_client: APIClient,
    ):
        url = f"{api_url_v1}/organizations/" f"{new_organization.id}/"
        actions = _get_options_actions(superuser_client, url)
        _assert_pattern_on_field(actions, "PATCH", "name", url)


# ---------------------------------------------------------------
# Read metadata — GET should NOT carry patterns
# ---------------------------------------------------------------
@pytest.mark.django_db
class TestOptionsGetNoPatterns:
    """GET fields should not carry pattern/patternDescription.

    EDAMetadata._customize_field_attributes strips write-only keys
    from GET actions; patterns are meaningful only for input fields.
    """

    def test_teams_get_no_pattern(
        self,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/teams/"
        actions = _get_options_actions(admin_client, url)
        _assert_no_pattern_on_field(actions, "GET", "name")

    def test_activations_get_no_pattern(
        self,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/activations/"
        actions = _get_options_actions(admin_client, url)
        _assert_no_pattern_on_field(actions, "GET", "name")


# ---------------------------------------------------------------
# Excluded fields should NOT carry patterns in POST/PATCH
# ---------------------------------------------------------------
@pytest.mark.django_db
class TestOptionsExcludedFieldsNoPatterns:
    """Fields listed in ``excluded_fields`` must not have patterns."""

    def test_awx_token_excluded(
        self,
        admin_client: APIClient,
    ):
        url = f"{api_url_v1}/users/me/awx-tokens/"
        actions = _get_options_actions(admin_client, url)
        post_fields = actions.get("POST", {})
        token_info = post_fields.get("token", {})
        # token is write-only so may be absent from POST action if
        # it was filtered out; when present it must not carry patterns
        if token_info:
            assert "pattern" not in token_info
