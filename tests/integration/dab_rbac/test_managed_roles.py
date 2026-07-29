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
from ansible_base.rbac.models import RoleDefinition
from django.test import override_settings
from rest_framework import status

from aap_eda.core import models
from aap_eda.core.management.commands.create_initial_data import ORG_ROLES
from tests.integration.constants import api_url_v1


@override_settings(ALLOW_LOCAL_ASSIGNING_JWT_ROLES=True)
@pytest.mark.django_db
def test_org_role_team_assignments(
    admin_client, default_organization, default_team, create_managed_org_roles
):
    for org_role in ORG_ROLES:
        # ignore Org Member role as it is not assignable to teams
        if org_role["name"] != "Organization Member":
            role = RoleDefinition.objects.get(name=org_role["name"])
            post_data = {
                "object_id": default_organization.id,
                "role_definition": role.id,
                "team": default_team.id,
            }
            response = admin_client.post(
                f"{api_url_v1}/role_team_assignments/", data=post_data
            )
            assert (
                response.status_code == status.HTTP_201_CREATED
            ), response.data


@override_settings(ALLOW_LOCAL_ASSIGNING_JWT_ROLES=True)
@pytest.mark.django_db
def test_org_role_user_assignments(
    admin_client, default_organization, default_user, create_managed_org_roles
):
    for org_role in ORG_ROLES:
        role = RoleDefinition.objects.get(name=org_role["name"])
        post_data = {
            "object_id": default_organization.id,
            "role_definition": role.id,
            "user": default_user.id,
        }
        response = admin_client.post(
            f"{api_url_v1}/role_user_assignments/", data=post_data
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data


@pytest.mark.django_db
def test_org_member_has_view_team_permission(create_managed_org_roles):
    """Regression test for AAP-79673.

    Organization Member role must include view_team so that org members
    can see teams within their organization.
    """
    role = RoleDefinition.objects.get(name="Organization Member")
    perm_codenames = set(role.permissions.values_list("codename", flat=True))
    assert (
        "view_team" in perm_codenames
    ), f"Organization Member should have view_team, got: {perm_codenames}"
    team_perms = {p for p in perm_codenames if p.endswith("_team")}
    assert team_perms == {"view_team"}, (
        "Organization Member should only have view_team"
        f" for teams, got: {team_perms}"
    )


@pytest.mark.django_db
def test_org_member_can_see_teams_in_org(
    user_api_client,
    default_user,
    default_organization,
    default_team,
    create_managed_org_roles,
):
    """Regression test for AAP-79673.

    A user with only the Organization Member role should be able to list
    and retrieve teams in their organization.
    """
    org_member_rd = RoleDefinition.objects.get(name="Organization Member")
    org_member_rd.give_permission(default_user, default_organization)

    response = user_api_client.get(f"{api_url_v1}/teams/")
    assert response.status_code == status.HTTP_200_OK
    team_ids = {t["id"] for t in response.data["results"]}
    assert (
        default_team.id in team_ids
    ), "Org member should see teams in their organization"

    response = user_api_client.get(f"{api_url_v1}/teams/{default_team.id}/")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_org_member_cannot_see_teams_in_other_org(
    user_api_client,
    default_user,
    default_organization,
    create_managed_org_roles,
):
    """Regression test for AAP-79673.

    Organization members must NOT see teams in organizations they
    don't belong to.  Without this negative test a regression that
    accidentally grants view_team globally would go undetected.
    """
    other_org = models.Organization.objects.create(
        name="Other Org",
        description="A separate organization",
    )
    other_team = models.Team.objects.create(
        name="Other Org Team",
        organization=other_org,
    )

    org_member_rd = RoleDefinition.objects.get(name="Organization Member")
    org_member_rd.give_permission(default_user, default_organization)

    response = user_api_client.get(f"{api_url_v1}/teams/")
    assert response.status_code == status.HTTP_200_OK
    team_ids = {t["id"] for t in response.data["results"]}
    assert (
        other_team.id not in team_ids
    ), "Org member should NOT see teams in organizations they do not belong to"

    response = user_api_client.get(f"{api_url_v1}/teams/{other_team.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_user_without_roles_sees_no_teams(
    user_api_client,
    default_organization,
    default_team,
    create_managed_org_roles,
):
    """Baseline test: a user with no role assignments should see no teams.

    This guards against the positive test passing trivially if the
    default queryset returns all teams.
    """
    response = user_api_client.get(f"{api_url_v1}/teams/")
    assert response.status_code == status.HTTP_200_OK
    assert (
        response.data["count"] == 0
    ), "User with no role assignments should see no teams"
