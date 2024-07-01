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
import pytest

from tests.integration.constants import api_url_v1


@pytest.mark.parametrize(
    "expected_slugs,use_shared_resource",
    [
        pytest.param(
            [
                "/status/",
                "/openapi.json",
                "/openapi.yaml",
                "/docs",
                "/redoc",
                "/auth/session/login/",
                "/auth/session/logout/",
                "/auth/token/refresh/",
                "/users/me/",
                "/projects/",
                "/rulebooks/",
                "/activations/",
                "/activation-instances/",
                "/audit-rules/",
                "/users/",
                "/event-streams/",
                "/users/me/awx-tokens/",
                "/credential-types/",
                "/eda-credentials/",
                "/decision-environments/",
                "/organizations/",
                "/teams/",
            ],
            True,
            id="with_shared_resource",
        ),
        pytest.param(
            [
                "/status/",
                "/role_definitions/",
                "/role_user_assignments/",
                "/role_team_assignments/",
                "/role_metadata/",
                "/service-index/metadata/",
                "/service-index/validate-local-account/",
                "/service-index/resources/",
                "/service-index/resource-types/",
                "/service-index/",
                "/openapi.json",
                "/openapi.yaml",
                "/docs",
                "/redoc",
                "/auth/session/login/",
                "/auth/session/logout/",
                "/auth/token/refresh/",
                "/users/me/",
                "/projects/",
                "/rulebooks/",
                "/activations/",
                "/activation-instances/",
                "/audit-rules/",
                "/users/",
                "/event-streams/",
                "/users/me/awx-tokens/",
                "/credential-types/",
                "/eda-credentials/",
                "/decision-environments/",
                "/organizations/",
                "/teams/",
            ],
            False,
            id="no_shared_resource",
        ),
    ],
)
@pytest.mark.django_db
def test_v1_root(admin_client, request, expected_slugs, use_shared_resource):
    if use_shared_resource:
        request.getfixturevalue("use_shared_resource_setting")
    response = admin_client.get(f"{api_url_v1}/")
    assert response.status_code == 200
    assert len(response.data) == len(expected_slugs)
    for slug in expected_slugs:
        assert any(
            slug in url for url in response.data.values()
        ), f"Expected slug {slug} not found in response"
