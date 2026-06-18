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

import time
from unittest.mock import patch

import pytest

from aap_eda.services.auth import (
    create_jwt_token,
    jwt_access_token,
    jwt_refresh_token,
    parse_jwt_token,
    validate_jwt_token,
)
from aap_eda.services.exceptions import InvalidTokenError


@pytest.mark.django_db
def test_create_jwt_token():
    token, refresh = create_jwt_token()

    assert token.count(".") == 2
    assert refresh.count(".") == 2

    validate_jwt_token(token, "access")
    validate_jwt_token(refresh, "refresh")

    assert {"user_id", "exp", "token_type"} <= parse_jwt_token(token).keys()
    assert {"user_id", "exp", "token_type"} <= parse_jwt_token(refresh).keys()


@pytest.mark.django_db
def test_validate_type_exception():
    token, _ = create_jwt_token()
    with pytest.raises(InvalidTokenError) as error_info:
        validate_jwt_token(token, "refresh")
    assert str(error_info.value) == "Invalid token type"


@pytest.mark.django_db
@patch("aap_eda.services.auth.settings.JWT_ACCESS_TOKEN_LIFETIME_MINUTES", "0")
def test_token_expired_exception():
    token, _ = create_jwt_token()
    time.sleep(1)
    with pytest.raises(InvalidTokenError) as error_info:
        parse_jwt_token(token)
    assert str(error_info.value) == "Expired token"


# ========== Activation Instance Scoping Tests ==========


@pytest.mark.django_db
def test_create_jwt_token_with_activation_instance_id():
    """Test creating tokens with activation_instance_id (int)."""
    activation_id = 123
    token, refresh = create_jwt_token(activation_instance_id=activation_id)

    assert token.count(".") == 2
    assert refresh.count(".") == 2

    # Parse and verify activation_instance_id is in payload
    token_payload = parse_jwt_token(token)
    refresh_payload = parse_jwt_token(refresh)

    assert token_payload["activation_instance_id"] == str(activation_id)
    assert refresh_payload["activation_instance_id"] == str(activation_id)
    assert token_payload["token_type"] == "access"
    assert refresh_payload["token_type"] == "refresh"


@pytest.mark.django_db
def test_create_jwt_token_with_uuid_activation_instance_id():
    """Test creating tokens with UUID activation_instance_id."""
    activation_id = "550e8400-e29b-41d4-a716-446655440000"
    token, refresh = create_jwt_token(activation_instance_id=activation_id)

    # Parse and verify UUID is preserved as string
    token_payload = parse_jwt_token(token)
    refresh_payload = parse_jwt_token(refresh)

    assert token_payload["activation_instance_id"] == activation_id
    assert refresh_payload["activation_instance_id"] == activation_id


@pytest.mark.django_db
def test_create_jwt_token_without_activation_instance_id():
    """Test creating tokens without activation_instance_id (legacy)."""
    token, refresh = create_jwt_token()

    # Parse and verify activation_instance_id is not in payload
    token_payload = parse_jwt_token(token)
    refresh_payload = parse_jwt_token(refresh)

    assert "activation_instance_id" not in token_payload
    assert "activation_instance_id" not in refresh_payload


@pytest.mark.django_db
def test_jwt_access_token_with_activation_instance_id():
    """Test jwt_access_token function with activation_instance_id."""
    from aap_eda.core.models.user import User

    user = User.objects.create(username="test_user")
    activation_id = "456"

    token = jwt_access_token(user.id, activation_instance_id=activation_id)
    payload = parse_jwt_token(token)

    assert payload["user_id"] == user.id
    assert payload["activation_instance_id"] == activation_id
    assert payload["token_type"] == "access"


@pytest.mark.django_db
def test_jwt_refresh_token_with_activation_instance_id():
    """Test jwt_refresh_token function with activation_instance_id."""
    from aap_eda.core.models.user import User

    user = User.objects.create(username="test_user")
    activation_id = "789"

    token = jwt_refresh_token(user.id, activation_instance_id=activation_id)
    payload = parse_jwt_token(token)

    assert payload["user_id"] == user.id
    assert payload["activation_instance_id"] == activation_id
    assert payload["token_type"] == "refresh"


@pytest.mark.django_db
def test_validate_jwt_token_with_matching_activation_instance_id():
    """Test validation succeeds when activation_instance_id matches."""
    activation_id = 123
    token, _ = create_jwt_token(activation_instance_id=activation_id)

    # Should not raise exception
    user = validate_jwt_token(
        token, "access", activation_instance_id=activation_id
    )
    assert user is not None


@pytest.mark.django_db
def test_validate_jwt_token_with_matching_activation_instance_id_uuid():
    """Test validation with UUID activation_instance_id."""
    activation_id = "550e8400-e29b-41d4-a716-446655440000"
    token, _ = create_jwt_token(activation_instance_id=activation_id)

    # Should not raise exception
    user = validate_jwt_token(
        token, "access", activation_instance_id=activation_id
    )
    assert user is not None


@pytest.mark.django_db
def test_validate_jwt_token_with_mismatched_activation_instance_id():
    """Test validation fails when activation_instance_id doesn't match."""
    token, _ = create_jwt_token(activation_instance_id=123)

    with pytest.raises(InvalidTokenError) as error_info:
        validate_jwt_token(token, "access", activation_instance_id=456)

    assert "Token is scoped to activation instance 123" in str(
        error_info.value
    )
    assert "but request is for activation instance 456" in str(
        error_info.value
    )


@pytest.mark.django_db
def test_validate_jwt_token_string_int_comparison():
    """Test that string and int IDs are compared correctly."""
    # Create token with int
    token, _ = create_jwt_token(activation_instance_id=123)

    # Validate with string - should work due to string comparison
    user = validate_jwt_token(token, "access", activation_instance_id="123")
    assert user is not None


@pytest.mark.django_db
def test_validate_jwt_token_without_activation_instance_id_legacy():
    """Test validation of legacy tokens without activation_instance_id."""
    # Create legacy token without activation_instance_id
    token, _ = create_jwt_token()

    # Should succeed when no activation_instance_id is required
    user = validate_jwt_token(token, "access")
    assert user is not None

    # Should fail when activation_instance_id is required
    with pytest.raises(InvalidTokenError) as error_info:
        validate_jwt_token(token, "access", activation_instance_id=123)

    assert "Token is not scoped to an activation instance" in str(
        error_info.value
    )


@pytest.mark.django_db
def test_validate_jwt_token_type_mismatch_with_activation_id():
    """Test that token type is still validated with activation_instance_id."""
    token, _ = create_jwt_token(activation_instance_id=123)

    with pytest.raises(InvalidTokenError) as error_info:
        validate_jwt_token(token, "refresh", activation_instance_id=123)

    assert str(error_info.value) == "Invalid token type"
