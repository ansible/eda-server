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
"""Unit tests for OAuth2 JWT required claim validation."""

from unittest.mock import patch

import pytest
from rest_framework.exceptions import AuthenticationFailed

from aap_eda.api.event_stream_authentication import Oauth2JwtAuthentication
from aap_eda.core.utils.credentials import _validate_yaml_dict

TOKEN_CLAIMS = {
    "iss": "https://idp.example.com",
    "sub": "sender-1",
    "groups": ["eda-senders", "ops"],
    "scope": "events:write",
    "email_verified": True,
    "level": 1,
    "realm_access": {"roles": ["eda", "admin"], "tier": "gold"},
}


def _authenticate(required_claims, claims=None):
    auth = Oauth2JwtAuthentication(
        jwks_url="https://idp.example.com/.well-known/jwks.json",
        audience="",
        access_token="Bearer dummy",
        required_claims=required_claims,
    )
    with (
        patch("aap_eda.api.event_stream_authentication.PyJWKClient"),
        patch(
            "aap_eda.api.event_stream_authentication.jwt_decode",
            return_value=TOKEN_CLAIMS if claims is None else claims,
        ),
    ):
        auth.authenticate()


@pytest.mark.parametrize(
    "required_claims",
    [
        None,
        {},
        {"iss": "https://idp.example.com"},
        {"iss": "https://idp.example.com", "sub": "sender-1"},
        # list claim contains a single required value
        {"groups": "eda-senders"},
        # list claim contains every required value
        {"groups": ["ops", "eda-senders"]},
        # single-item list against a scalar claim
        {"scope": ["events:write"]},
        {"email_verified": True},
        {"level": 1},
        # nested objects are matched recursively
        {"realm_access": {"roles": "eda"}},
        {"realm_access": {"roles": ["admin", "eda"], "tier": "gold"}},
    ],
)
def test_required_claims_satisfied(required_claims):
    _authenticate(required_claims)


@pytest.mark.parametrize(
    ("required_claims", "error"),
    [
        ({"tenant": "acme"}, "missing required claim 'tenant'"),
        ({"iss": "https://evil.example.com"}, "claim 'iss' does not match"),
        ({"groups": "admins"}, "claim 'groups' does not match"),
        # every required value must be present in the list claim
        ({"groups": ["eda-senders", "admins"]}, "claim 'groups' does not"),
        # a scalar claim can't satisfy several required values
        ({"scope": ["events:write", "x"]}, "claim 'scope' does not match"),
        # bool and int must not be treated as equal
        ({"level": True}, "claim 'level' does not match"),
        ({"email_verified": 1}, "claim 'email_verified' does not match"),
        ({"sub": {"id": "sender-1"}}, "claim 'sub' does not match"),
        (
            {"realm_access": {"roles": "superuser"}},
            "claim 'realm_access.roles' does not match",
        ),
        (
            {"realm_access": {"region": "us"}},
            "missing required claim 'realm_access.region'",
        ),
    ],
)
def test_required_claims_not_satisfied(required_claims, error):
    with pytest.raises(AuthenticationFailed, match=error):
        _authenticate(required_claims)


def test_required_claims_error_does_not_leak_values():
    with pytest.raises(AuthenticationFailed) as exc_info:
        _authenticate({"iss": "https://expected.example.com"})

    message = str(exc_info.value.detail)
    assert "expected.example.com" not in message
    assert "idp.example.com" not in message


@pytest.mark.parametrize(
    ("value", "errors"),
    [
        ('{"iss": "https://idp.example.com"}', []),
        ("iss: https://idp.example.com\ngroups:\n  - eda\n", []),
        ("{ }", []),
        ("iss: [unclosed", ["Must be in JSON or YAML format"]),
        ("- a\n- b\n", ["Must be in object format"]),
        ("just a string", ["Must be in object format"]),
        ("42", ["Must be in object format"]),
    ],
)
def test_validate_yaml_dict(value, errors):
    assert _validate_yaml_dict(value) == errors
