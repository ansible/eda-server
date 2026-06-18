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

"""Tests for auth serializers, specifically RefreshTokenSerializer
scope preservation.
"""

import pytest

from aap_eda.api.serializers.auth import RefreshTokenSerializer
from aap_eda.services.auth import create_jwt_token


@pytest.mark.django_db
class TestRefreshTokenSerializer:
    """Tests for RefreshTokenSerializer activation_instance_id
    extraction.
    """

    def test_validate_extracts_activation_instance_id_from_scoped_token(
        self,
    ):
        """Test that serializer extracts activation_instance_id from
        scoped refresh token.
        """
        activation_id = "123"
        _, refresh_token = create_jwt_token(
            activation_instance_id=activation_id
        )

        serializer = RefreshTokenSerializer(data={"refresh": refresh_token})
        assert serializer.is_valid()

        # Verify activation_instance_id was extracted and stored
        assert hasattr(serializer, "activation_instance_id")
        assert serializer.activation_instance_id == activation_id
        assert serializer.user is not None

    def test_validate_extracts_activation_instance_id_uuid(self):
        """Test that serializer extracts UUID activation_instance_id."""
        activation_id = "550e8400-e29b-41d4-a716-446655440000"
        _, refresh_token = create_jwt_token(
            activation_instance_id=activation_id
        )

        serializer = RefreshTokenSerializer(data={"refresh": refresh_token})
        assert serializer.is_valid()

        assert serializer.activation_instance_id == activation_id

    def test_validate_sets_none_for_legacy_token_without_activation_id(
        self,
    ):
        """Test that serializer sets activation_instance_id to None for
        legacy tokens.
        """
        # Create legacy token without activation_instance_id
        _, refresh_token = create_jwt_token()

        serializer = RefreshTokenSerializer(data={"refresh": refresh_token})
        assert serializer.is_valid()

        # Verify activation_instance_id is None for legacy tokens
        assert hasattr(serializer, "activation_instance_id")
        assert serializer.activation_instance_id is None
        assert serializer.user is not None

    def test_validate_fails_with_invalid_token(self):
        """Test that serializer fails validation with invalid token."""
        serializer = RefreshTokenSerializer(data={"refresh": "invalid_token"})

        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors
        assert "Invalid token" in str(serializer.errors)

    def test_validate_fails_with_expired_token(self):
        """Test that serializer fails validation with expired token."""
        from unittest.mock import patch

        # Create token with 0 lifetime (immediately expired)
        with patch(
            "aap_eda.services.auth.settings.JWT_REFRESH_TOKEN_LIFETIME_DAYS",
            "0",
        ):
            _, refresh_token = create_jwt_token()

        import time

        time.sleep(1)

        serializer = RefreshTokenSerializer(data={"refresh": refresh_token})

        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors
        assert "Invalid token" in str(serializer.errors)

    def test_validate_fails_with_access_token_instead_of_refresh(self):
        """Test that serializer fails when access token is used instead of
        refresh token.
        """
        # Create tokens and use access token instead of refresh
        access_token, _ = create_jwt_token(activation_instance_id="123")

        serializer = RefreshTokenSerializer(data={"refresh": access_token})

        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors
        assert "Invalid token" in str(serializer.errors)

    def test_validate_preserves_user_from_token(self):
        """Test that serializer properly extracts and stores user from
        token.
        """
        from aap_eda.core.models.user import User

        # Get the service user that will be in the token
        user, _ = User.objects.get_or_create(
            username="_token_service_user",
            is_service_account=True,
        )

        _, refresh_token = create_jwt_token(activation_instance_id="123")

        serializer = RefreshTokenSerializer(data={"refresh": refresh_token})
        assert serializer.is_valid()

        assert serializer.user.id == user.id
        assert serializer.user.username == "_token_service_user"
