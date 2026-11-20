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

import json
import time
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from rest_framework.exceptions import AuthenticationFailed

from aap_eda.api.event_stream_authentication import Oauth2JwtAuthentication
from aap_eda.api.views.external_event_stream import ExternalEventStreamViewSet
from aap_eda.core.utils.credentials import _validate_yaml_dict

TOKEN_CLAIMS = {
    "iss": "https://idp.example.com",
    "sub": "sender-1",
    "groups": ["eda-senders", "ops"],
    "scope": "events:write",
    "email_verified": True,
    "level": 1,
    "realm_access": {"roles": ["eda", "admin"], "tier": "gold"},
    "permissions": [
        {"name": "eda", "admin": True, "level": 1},
        {"name": "ops", "admin": False, "level": 0},
    ],
    "matrix": [[1, 0], [True, False]],
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
        # dict and nested-list values inside list claims
        {"permissions": [{"name": "eda", "admin": True, "level": 1}]},
        {"permissions": [{"name": "ops", "admin": False, "level": 0}]},
        {"matrix": [[True, False]]},
        {"matrix": [[1, 0], [True, False]]},
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
        # bool/int must not match inside dicts in a list claim; each of
        # these would match a token element under Python's loose ==
        (
            {"permissions": [{"name": "eda", "admin": 1, "level": 1}]},
            "claim 'permissions' does not match",
        ),
        (
            {"permissions": [{"name": "eda", "admin": True, "level": True}]},
            "claim 'permissions' does not match",
        ),
        (
            {"permissions": [{"name": "ops", "admin": 0, "level": 0}]},
            "claim 'permissions' does not match",
        ),
        # bool/int must not match inside nested lists (loose == would
        # match [True, 0] to [1, 0] and [1, False] to [True, False])
        ({"matrix": [[True, 0]]}, "claim 'matrix' does not match"),
        ({"matrix": [[1, False]]}, "claim 'matrix' does not match"),
        # element shape must match exactly
        ({"matrix": [[1]]}, "claim 'matrix' does not match"),
        (
            {"permissions": [{"name": "eda", "admin": True}]},
            "claim 'permissions' does not match",
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


def test_required_claims_defaults_to_none():
    """Callers that predate required_claims keep working unchanged."""
    auth = Oauth2JwtAuthentication(
        jwks_url="https://idp.example.com/.well-known/jwks.json",
        audience="",
        access_token="Bearer dummy",
    )
    assert auth.required_claims is None
    with (
        patch("aap_eda.api.event_stream_authentication.PyJWKClient"),
        patch(
            "aap_eda.api.event_stream_authentication.jwt_decode",
            return_value={},
        ),
    ):
        auth.authenticate()


# YAML/JSON configuration goes through the same parser used at request
# time, so these cover what an admin can actually type into the field.
DEEP_CLAIMS = {
    "iss": "https://idp.example.com",
    "https://example.com/claims": {"roles": ["eda"]},
    "a": {"b": {"c": {"d": {"e": ["x", "y"], "f": None}}}},
    "verified": True,
    "count": 1,
    "zip": "02134",
    "empty_obj": {},
    "empty_list": [],
}


@pytest.mark.parametrize(
    "yaml_value",
    [
        # deeply nested mapping, YAML block style
        "a:\n  b:\n    c:\n      d:\n        e: x\n",
        # deeply nested mapping, JSON flow style
        '{"a": {"b": {"c": {"d": {"e": ["y", "x"]}}}}}',
        # explicit null requires the claim to be present and null
        "a: {b: {c: {d: {f: null}}}}",
        # namespaced claim names containing ':' '/' and '.'
        '"https://example.com/claims":\n  roles: [eda]\n',
        # quoted scalars stay strings
        'zip: "02134"',
        # empty requirements only check the claim exists with that type
        "empty_obj: { }",
        "empty_list: []",
        # YAML 1.1 boolean spellings are parsed as booleans
        "verified: yes",
        "verified: on",
    ],
)
def test_required_claims_from_yaml_satisfied(yaml_value):
    required = ExternalEventStreamViewSet._parse_required_claims(yaml_value)
    _authenticate(required, claims=DEEP_CLAIMS)


@pytest.mark.parametrize(
    ("yaml_value", "error"),
    [
        (
            "a:\n  b:\n    c:\n      d:\n        e: z\n",
            "claim 'a.b.c.d.e' does not match",
        ),
        ("a: {b: {c: {d: {g: 1}}}}", "missing required claim 'a.b.c.d.g'"),
        ("a: {b: {c: {d: {e: {x: 1}}}}}", "claim 'a.b.c.d.e' does not match"),
        ("a: {b: {c: 1}}", "claim 'a.b.c' does not match"),
        # unquoted 02134 is an int in YAML, not the string claim
        ("zip: 02134", "claim 'zip' does not match"),
        # numbers and strings are never coerced
        ('count: "1"', "claim 'count' does not match"),
        ("verified: 1", "claim 'verified' does not match"),
        # an empty object/list still requires the matching type
        ("count: { }", "claim 'count' does not match"),
        # non-string keys can never match JWT (JSON) claim names
        ("1: one", "missing required claim '1'"),
        ("true: x", "missing required claim 'True'"),
        # YAML timestamps parse to dates, which JWT claims never are
        ("iss: 2024-01-01", "claim 'iss' does not match"),
    ],
)
def test_required_claims_from_yaml_not_satisfied(yaml_value, error):
    required = ExternalEventStreamViewSet._parse_required_claims(yaml_value)
    with pytest.raises(AuthenticationFailed, match=error):
        _authenticate(required, claims=DEEP_CLAIMS)


# End-to-end tests below use real RS256 tokens verified against a JWKS.
# Only the JWKS HTTP fetch is stubbed; PyJWKClient key selection and
# jwt.decode signature/claim verification run for real.
JWKS_URL = "https://idp.example.com/.well-known/jwks.json"
KID = "test-key"


def _rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def signing_key():
    return _rsa_key()


@pytest.fixture(scope="module")
def jwks(signing_key):
    jwk = json.loads(
        jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key())
    )
    jwk.update({"kid": KID, "use": "sig", "alg": "RS256"})
    return {"keys": [jwk]}


def _sign(key, claims, kid=KID, algorithm="RS256"):
    now = int(time.time())
    payload = {"iat": now, "nbf": now, "exp": now + 300, **claims}
    return jwt.encode(payload, key, algorithm=algorithm, headers={"kid": kid})


def _authenticate_signed(jwks, token, required_claims=None, audience=""):
    auth = Oauth2JwtAuthentication(
        jwks_url=JWKS_URL,
        audience=audience,
        access_token=f"Bearer {token}",
        required_claims=required_claims,
    )
    with patch.object(jwt.PyJWKClient, "fetch_data", return_value=jwks):
        auth.authenticate()


@pytest.mark.parametrize(
    ("required_claims", "audience"),
    [
        (None, ""),
        ({}, ""),
        ({"iss": "https://idp.example.com"}, ""),
        ({"groups": "eda-senders", "realm_access": {"roles": "eda"}}, ""),
        ({"iss": "https://idp.example.com"}, "eda"),
    ],
)
def test_signed_jwt_satisfies_required_claims(
    signing_key, jwks, required_claims, audience
):
    token = _sign(signing_key, {**TOKEN_CLAIMS, "aud": "eda"})
    _authenticate_signed(jwks, token, required_claims, audience)


@pytest.mark.parametrize(
    ("required_claims", "error"),
    [
        ({"iss": "https://evil.example.com"}, "claim 'iss' does not match"),
        ({"tenant": "acme"}, "missing required claim 'tenant'"),
        ({"realm_access": {"roles": "root"}}, "'realm_access.roles' does"),
    ],
)
def test_signed_jwt_fails_required_claims(
    signing_key, jwks, required_claims, error
):
    token = _sign(signing_key, TOKEN_CLAIMS)
    with pytest.raises(AuthenticationFailed, match=error):
        _authenticate_signed(jwks, token, required_claims)


def test_signed_jwt_wrong_key_rejected_before_claims(jwks):
    """Matching claims must not help a token signed by an unknown key."""
    token = _sign(_rsa_key(), TOKEN_CLAIMS)
    with pytest.raises(AuthenticationFailed, match="Signature verification"):
        _authenticate_signed(jwks, token, {"iss": "https://idp.example.com"})


def test_signed_jwt_unknown_kid_rejected(signing_key, jwks):
    token = _sign(signing_key, TOKEN_CLAIMS, kid="other-key")
    with pytest.raises(AuthenticationFailed, match="Unable to find a signing"):
        _authenticate_signed(jwks, token, {"iss": "https://idp.example.com"})


def test_signed_jwt_expired_rejected(signing_key, jwks):
    token = _sign(signing_key, {**TOKEN_CLAIMS, "exp": int(time.time()) - 60})
    with pytest.raises(AuthenticationFailed, match="expired"):
        _authenticate_signed(jwks, token, {"iss": "https://idp.example.com"})


def test_signed_jwt_wrong_audience_rejected(signing_key, jwks):
    token = _sign(signing_key, {**TOKEN_CLAIMS, "aud": "other"})
    with pytest.raises(AuthenticationFailed, match="Audience"):
        _authenticate_signed(
            jwks, token, {"iss": "https://idp.example.com"}, audience="eda"
        )


def test_signed_jwt_tampered_payload_rejected(signing_key, jwks):
    """Rewriting claims to satisfy requirements breaks the signature."""
    header, _, signature = _sign(signing_key, TOKEN_CLAIMS).split(".")
    forged = jwt.utils.base64url_encode(
        json.dumps({**TOKEN_CLAIMS, "tenant": "acme"}).encode()
    ).decode()
    with pytest.raises(AuthenticationFailed, match="Signature verification"):
        _authenticate_signed(
            jwks, f"{header}.{forged}.{signature}", {"tenant": "acme"}
        )


def test_signed_jwt_hs256_rejected(jwks):
    """Algorithm confusion: an HMAC token is never accepted."""
    token = jwt.encode(
        {**TOKEN_CLAIMS, "exp": int(time.time()) + 300},
        "secret",
        algorithm="HS256",
        headers={"kid": KID},
    )
    with pytest.raises(AuthenticationFailed, match="alg value is not allowed"):
        _authenticate_signed(jwks, token, {"iss": "https://idp.example.com"})
