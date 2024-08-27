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
