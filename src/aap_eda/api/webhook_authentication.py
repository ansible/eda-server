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

import base64
import hmac
import logging
from hashlib import sha256
from urllib.parse import urljoin

import ecdsa
import jwt
import requests
from ecdsa.util import sigdecode_der
from rest_framework.exceptions import AuthenticationFailed

from aap_eda.core.enums import HMACFormatType

logger = logging.getLogger(__name__)


def validate_hmac_auth(
    secret: str,
    fmt: str,
    prefix: str,
    body: bytes,
    signature: str,
    algorithm: str,
):
    hash_object = hmac.new(
        secret,
        msg=body,
        digestmod=algorithm or "sha256",
    )
    if not fmt:
        fmt = HMACFormatType.BASE64

    if fmt == HMACFormatType.HEX:
        expected_signature = prefix + hash_object.hexdigest()
    elif fmt == HMACFormatType.BASE64:
        expected_signature = (
            prefix + base64.b64encode(hash_object.digest()).decode()
        )

    if not hmac.compare_digest(expected_signature, signature):
        message = "Signature mismatch, check your payload and secret"
        logger.warning(message)
        raise AuthenticationFailed(message)


def validate_token_auth(secret: str, token: str):
    if secret != _token_sans_bearer(token):
        message = "Token mismatch, check your token"
        logger.warning(message)
        raise AuthenticationFailed(message)


def validate_mtls_auth(subject: str, cert_subject: str):
    if subject and subject != cert_subject:
        message = f"Subject Name mismatch : {cert_subject}"
        logger.warning(message)
        raise AuthenticationFailed(message)


def validate_basic_auth(username: str, password: str, auth_str: str):
    if auth_str.startswith("Basic"):
        auth_str = auth_str.split("Basic ")[1]
    user_pass = f"{username}:{password}"
    b64_value = base64.b64encode(user_pass.encode()).decode()
    if auth_str != b64_value:
        message = "Credential mismatch"
        logger.warning(message)
        raise AuthenticationFailed(message)


def validate_jwt_access_token(jwks_url: str, audience: str, access_token: str):
    if not jwt.algorithms.has_crypto:
        raise Exception(
            "No crypto support for JWT, "
            "please install the cryptography dependency"
        )
    try:
        access_token = _token_sans_bearer(access_token)
        if not bool(jwks_url):
            # Not safe to do this
            url = jwt.decode(
                access_token, options={"verify_signature": False}
            )["iss"]
            jwks_url = urljoin(url, ".well-known/jwks.json")
            logger.error(f"JWKS URL is {jwks_url}")

        jwks_client = jwt.PyJWKClient(
            jwks_url, cache_jwk_set=True, lifespan=360
        )
        options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iat": True,
            "verify_aud": False,
        }

        if bool(audience):
            options["verify_aud"] = True

        signing_key = jwks_client.get_signing_key_from_jwt(access_token)
        data = jwt.decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            options=options,
        )
        return data
    except jwt.exceptions.PyJWTError as err:
        message = f"JWT Error {err}"
        logger.warning(message)
        raise AuthenticationFailed(message)


def validate_oauth_access_token(
    introspection_url: str, token: str, client_id: str, client_secret: str
):
    data = {
        "token": _token_sans_bearer(token),
        "token_type_hint": "access_token",
    }
    auth = (client_id, client_secret)
    # For keycloak this data is not in JSON format instead of www-url-encoded
    response = requests.post(introspection_url, data=data, auth=auth)
    if response.status_code != 200:
        message = f"Introspection Error {response.status_code} {response.text}"
        logger.warning(message)
        raise AuthenticationFailed(message)

    response_data = response.json()
    if not response_data.get("active", False):
        message = "User is not active"
        logger.warning(message)
        raise AuthenticationFailed(message)


def validate_ecdsa(
    message: bytes, public_key_pem: str, signature: str, content_prefix: str
):
    logger.debug(f"Public Key {public_key_pem}")
    logger.debug(f"Signature {signature}")
    logger.debug(f"Content Prefix {content_prefix}")
    public_key = ecdsa.VerifyingKey.from_pem(public_key_pem.encode())
    signature = base64.b64decode(signature)

    message_bytes = bytearray()
    if content_prefix:
        message_bytes.extend(content_prefix.encode())

    message_bytes.extend(message)
    if not public_key.verify(
        signature, bytes(message_bytes), sha256, sigdecode=sigdecode_der
    ):
        error = "ECDSA signature does not match"
        logger.warning(error)
        raise AuthenticationFailed(error)


def _token_sans_bearer(token: str) -> str:
    if token.startswith("Bearer"):
        return token.split("Bearer ")[1]
    return token
