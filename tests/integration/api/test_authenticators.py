#  Copyright 2023 Red Hat, Inc.
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

# Experimental LDAP Integration https://issues.redhat.com/browse/AAP-16938
# All of this file includes minimal sanity tests for experimental LDAP
# integration changes using django-ansible-base which will be removed later

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from tests.integration.constants import api_url_v1

TEST_LDAP_AUTHENTICATOR = {
    "name": "Dev LDAP Container",
    "enabled": True,
    "configuration": {
        "BIND_DN": "cn=admin,dc=example,dc=org",
        "BIND_PASSWORD": "admin",
        "CONNECTION_OPTIONS": {"OPT_REFERRALS": 0, "OPT_NETWORK_TIMEOUT": 30},
        "GROUP_SEARCH": [
            "ou=groups,dc=example,dc=org",
            "SCOPE_SUBTREE",
            "(objectClass=groupOfNames)",
        ],
        "GROUP_TYPE": "MemberDNGroupType",
        "GROUP_TYPE_PARAMS": {"name_attr": "cn", "member_attr": "member"},
        "SERVER_URI": ["ldap://host.containers.internal:389"],
        "START_TLS": True,
        "USER_ATTR_MAP": {
            "email": "mail",
            "last_name": "sn",
            "first_name": "givenName",
        },
        "USER_DN_TEMPLATE": "cn=%(user)s,ou=users,dc=example,dc=org",
        "USER_SEARCH": [
            "ou=users,dc=example,dc=org",
            "SCOPE_SUBTREE",
            "(cn=%(user)s)",
        ],
    },
    "type": "aap_eda.core.authenticator_plugins.ldap",
}

TEST_AUTHENTICATOR_MAP = {
    "name": "Admin",
    "order": 1,
    "organization": "Admin",
    "revoke": True,
    "team": None,
    "triggers": {
        "groups": {"has_or": ["cn=admins,ou=groups,dc=example,dc=org"]}
    },
    "map_type": "is_superuser",
}


@pytest.mark.django_db
def test_create_authenticators(client: APIClient):
    response = client.post(
        f"{api_url_v1}/authenticators/",
        data=TEST_LDAP_AUTHENTICATOR,
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.data
    assert data["name"] == TEST_LDAP_AUTHENTICATOR["name"]
    assert data["enabled"] == TEST_LDAP_AUTHENTICATOR["enabled"]
    assert (
        data["configuration"]["SERVER_URI"]
        == TEST_LDAP_AUTHENTICATOR["configuration"]["SERVER_URI"]
    )
    assert data["type"] == TEST_LDAP_AUTHENTICATOR["type"]


@pytest.mark.django_db
def test_list_authenticators(client: APIClient):
    response = client.get(f"{api_url_v1}/authenticators/")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_create_authenticator_maps(client: APIClient):
    auth_response = client.post(
        f"{api_url_v1}/authenticators/",
        data=TEST_LDAP_AUTHENTICATOR,
    )

    response = client.post(
        f"{api_url_v1}/authenticator_maps/",
        data={
            "authenticator": auth_response.data["id"],
            **TEST_AUTHENTICATOR_MAP,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.data
    assert data["name"] == TEST_AUTHENTICATOR_MAP["name"]
    assert data["organization"] == TEST_AUTHENTICATOR_MAP["organization"]
    assert data["map_type"] == TEST_AUTHENTICATOR_MAP["map_type"]


@pytest.mark.django_db
def test_list_authenticator_maps(client: APIClient):
    response = client.get(f"{api_url_v1}/authenticator_maps/")
    assert response.status_code == status.HTTP_200_OK
