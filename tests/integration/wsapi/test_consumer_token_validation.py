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

"""Tests for WebSocket consumer JWT token validation.

Tests JWT token validation with activation instance scoping.
"""

import pytest
from channels.db import database_sync_to_async

from aap_eda.services.auth import create_jwt_token
from aap_eda.services.exceptions import InvalidTokenError
from aap_eda.wsapi.consumers import AnsibleRulebookConsumer


@pytest.fixture
def mock_consumer():
    """Create a mock consumer with scope headers."""
    consumer = AnsibleRulebookConsumer()
    consumer.scope = {"headers": []}
    return consumer


def set_consumer_token(consumer, token):
    """Set authorization header in consumer scope."""
    consumer.scope["headers"] = [
        (b"authorization", f"Bearer {token}".encode())
    ]


@pytest.mark.django_db
class TestConsumerTokenValidation:
    """Tests for consumer token scope validation."""

    def test_get_token_payload_success(self, mock_consumer):
        """Test successfully extracting token payload."""
        token, _ = create_jwt_token(activation_instance_id=123)
        set_consumer_token(mock_consumer, token)

        payload = mock_consumer._get_token_payload()

        assert payload is not None
        assert payload["activation_instance_id"] == "123"
        assert payload["token_type"] == "access"

    def test_get_token_payload_caching(self, mock_consumer):
        """Test that token payload is cached after first parse."""
        token, _ = create_jwt_token(activation_instance_id=123)
        set_consumer_token(mock_consumer, token)

        # First call
        payload1 = mock_consumer._get_token_payload()
        # Second call should return cached value
        payload2 = mock_consumer._get_token_payload()

        assert payload1 is payload2  # Same object reference

    def test_get_token_payload_no_auth_header(self, mock_consumer):
        """Test error when no authorization header is present."""
        mock_consumer.scope["headers"] = []

        with pytest.raises(InvalidTokenError) as exc_info:
            mock_consumer._get_token_payload()

        assert "No authorization header found" in str(exc_info.value)

    def test_get_token_payload_invalid_format(self, mock_consumer):
        """Test error when authorization header has invalid format."""
        mock_consumer.scope["headers"] = [(b"authorization", b"InvalidFormat")]

        with pytest.raises(InvalidTokenError) as exc_info:
            mock_consumer._get_token_payload()

        assert "Invalid authorization header format" in str(exc_info.value)

    def test_get_token_payload_not_bearer(self, mock_consumer):
        """Test error when authorization header is not Bearer type."""
        mock_consumer.scope["headers"] = [
            (b"authorization", b"Basic dXNlcjpwYXNz")
        ]

        with pytest.raises(InvalidTokenError) as exc_info:
            mock_consumer._get_token_payload()

        assert "Invalid authorization header format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_token_scope_matching_id(self, mock_consumer):
        """Test validation succeeds when activation_instance_id matches."""
        activation_id = 123
        token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=activation_id
        )
        set_consumer_token(mock_consumer, token)

        # Should not raise exception
        await mock_consumer._validate_token_scope(activation_id)

    @pytest.mark.asyncio
    async def test_validate_token_scope_matching_uuid(self, mock_consumer):
        """Test validation succeeds with UUID activation_instance_id."""
        activation_id = "550e8400-e29b-41d4-a716-446655440000"
        token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=activation_id
        )
        set_consumer_token(mock_consumer, token)

        # Should not raise exception
        await mock_consumer._validate_token_scope(activation_id)

    @pytest.mark.asyncio
    async def test_validate_token_scope_string_int_matching(
        self, mock_consumer
    ):
        """Test validation with string vs int comparison."""
        token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=123
        )
        set_consumer_token(mock_consumer, token)

        # Should work with string "123"
        await mock_consumer._validate_token_scope("123")

    @pytest.mark.asyncio
    async def test_validate_token_scope_mismatched_id(self, mock_consumer):
        """Test validation fails when activation_instance_id doesn't match."""
        token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=123
        )
        set_consumer_token(mock_consumer, token)

        with pytest.raises(InvalidTokenError) as exc_info:
            await mock_consumer._validate_token_scope(456)

        assert "Token is scoped to activation instance 123" in str(
            exc_info.value
        )
        assert "but message is for activation instance 456" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_validate_token_scope_legacy_token_without_scope(
        self, mock_consumer
    ):
        """Test legacy tokens without activation_instance_id are allowed.

        Legacy tokens should be allowed with async warning.
        """
        # Create legacy token without activation_instance_id
        token, _ = await database_sync_to_async(create_jwt_token)()
        set_consumer_token(mock_consumer, token)

        # Should not raise exception - legacy tokens are allowed
        # Note: This is now an async method that logs warning
        await mock_consumer._validate_token_scope(123)

    @pytest.mark.asyncio
    async def test_validate_token_scope_scoped_token_validates_mismatch(
        self, mock_consumer
    ):
        """Test that scoped tokens reject mismatched activation_instance_id."""
        # Token with activation_instance_id
        token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=123
        )
        set_consumer_token(mock_consumer, token)

        # Should still fail on mismatch
        with pytest.raises(InvalidTokenError) as exc_info:
            await mock_consumer._validate_token_scope(456)

        assert "Token is scoped to activation instance 123" in str(
            exc_info.value
        )


@pytest.mark.django_db
class TestConsumerRefreshTokenRejection:
    """Tests for refresh token rejection in WebSocket auth."""

    def test_get_token_payload_rejects_refresh_token(self, mock_consumer):
        """Test that refresh tokens are rejected in WebSocket auth.

        Security fix: Refresh tokens should only be used to obtain new
        access tokens, never for direct WebSocket authentication.
        """
        # Create token pair - use refresh token (index 1)
        _, refresh_token = create_jwt_token(activation_instance_id=123)
        set_consumer_token(mock_consumer, refresh_token)

        with pytest.raises(InvalidTokenError) as exc_info:
            mock_consumer._get_token_payload()

        assert "Invalid token type 'refresh'" in str(exc_info.value)
        assert "Only access tokens are permitted" in str(exc_info.value)

    def test_get_token_payload_accepts_access_token(self, mock_consumer):
        """Test that access tokens are accepted in WebSocket auth."""
        # Create token pair - use access token (index 0)
        access_token, _ = create_jwt_token(activation_instance_id=123)
        set_consumer_token(mock_consumer, access_token)

        # Should not raise exception
        payload = mock_consumer._get_token_payload()

        assert payload is not None
        assert payload["token_type"] == "access"
        assert payload["activation_instance_id"] == "123"

    def test_get_token_payload_rejects_missing_token_type(self, mock_consumer):
        """Test rejection of tokens without token_type field.

        Legacy tokens or malformed tokens without token_type should
        be rejected.
        """
        from datetime import datetime, timedelta

        import jwt
        from django.conf import settings

        # Create malformed token without token_type (but valid exp)
        payload = {
            "user_id": 1,
            "exp": datetime.now() + timedelta(days=1),
            "activation_instance_id": "123",
            # Missing token_type field
        }
        malformed_token = jwt.encode(
            payload, settings.SECRET_KEY, algorithm="HS256"
        )
        set_consumer_token(mock_consumer, malformed_token)

        with pytest.raises(InvalidTokenError) as exc_info:
            mock_consumer._get_token_payload()

        assert "Invalid token type 'None'" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_receive_rejects_refresh_token_in_job_message(
        self, mock_consumer
    ):
        """Test that JOB messages with refresh token are rejected.

        Integration test: Verify refresh token rejection works in
        the full receive() flow.
        """
        from unittest.mock import AsyncMock, patch

        from channels.db import database_sync_to_async

        # Use refresh token (index 1) instead of access token
        _, refresh_token = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=123
        )
        set_consumer_token(mock_consumer, refresh_token)

        # Mock the close method and _set_log_tracking_id
        mock_consumer.close = AsyncMock()
        mock_consumer._set_log_tracking_id = AsyncMock()

        # Mock handle_jobs to verify it's NOT called on rejection
        with patch.object(
            mock_consumer, "handle_jobs", new_callable=AsyncMock
        ) as mock_handle_jobs:
            # Try to send a JOB message with refresh token
            await mock_consumer.receive(
                text_data='{"type": "Job", "ansible_rulebook_id": 123, '
                '"job_id": "test-job-123", "name": "Test Job", '
                '"action": "run_playbook", "ruleset": "test_ruleset", '
                '"hosts": "localhost", "rule": "test_rule"}'
            )

            # Verify message was NOT dispatched
            mock_handle_jobs.assert_not_called()
            # Verify connection was closed with auth failure code
            mock_consumer.close.assert_called_once_with(code=4003)

    @pytest.mark.asyncio
    async def test_receive_accepts_access_token_in_job_message(
        self, mock_consumer
    ):
        """Test that JOB messages with access token are accepted.

        Integration test: Verify access token works in full receive() flow.
        """
        from unittest.mock import AsyncMock, patch

        from channels.db import database_sync_to_async

        # Use access token (index 0)
        access_token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=123
        )
        set_consumer_token(mock_consumer, access_token)

        # Mock the close method and _set_log_tracking_id
        mock_consumer.close = AsyncMock()
        mock_consumer._set_log_tracking_id = AsyncMock()

        # Send a JOB message with access token
        with patch.object(
            mock_consumer, "handle_jobs", new_callable=AsyncMock
        ) as mock_handle_jobs:
            await mock_consumer.receive(
                text_data='{"type": "Job", "ansible_rulebook_id": 123, '
                '"job_id": "test-job-123", "name": "Test Job", '
                '"action": "run_playbook", "ruleset": "test_ruleset", '
                '"hosts": "localhost", "rule": "test_rule"}'
            )

            # Should succeed
            mock_consumer.close.assert_not_called()
            mock_handle_jobs.assert_called_once()


@pytest.mark.django_db
class TestConsumerTokenScopeIntegration:
    """Integration tests for token scope validation in consumer."""

    @pytest.mark.asyncio
    async def test_token_validation_with_matching_scope(self, mock_consumer):
        """Test that validation passes when token scope matches."""
        # This test verifies the full flow works correctly
        token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=123
        )
        set_consumer_token(mock_consumer, token)

        # Should not raise - validation succeeds
        await mock_consumer._validate_token_scope(123)
        # String comparison works
        await mock_consumer._validate_token_scope("123")

    @pytest.mark.asyncio
    async def test_token_validation_rejects_wrong_scope(self, mock_consumer):
        """Test that validation fails when token scope doesn't match."""
        token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=123
        )
        set_consumer_token(mock_consumer, token)

        # Should raise InvalidTokenError
        with pytest.raises(InvalidTokenError) as exc_info:
            await mock_consumer._validate_token_scope(456)

        assert "123" in str(exc_info.value)
        assert "456" in str(exc_info.value)


@pytest.mark.django_db
class TestConsumerLegacyTokenWarning:
    """Tests for legacy token warning functionality."""

    @pytest.mark.asyncio
    async def test_legacy_token_warning_logged_once(self, mock_consumer):
        """Test warning is logged only once per connection.

        Legacy tokens should trigger a warning only once per connection.
        """
        from unittest.mock import AsyncMock, patch

        from channels.db import database_sync_to_async

        # Mock _get_activation_name to return the test activation name
        mock_consumer._get_activation_name = AsyncMock(
            return_value="Test Activation"
        )

        # Create legacy token
        token, _ = await database_sync_to_async(create_jwt_token)()
        set_consumer_token(mock_consumer, token)

        # Call validate multiple times with a test activation ID
        activation_id = 123
        with patch("aap_eda.wsapi.consumers.logger") as mock_logger:
            await mock_consumer._validate_token_scope(activation_id)
            await mock_consumer._validate_token_scope(activation_id)
            await mock_consumer._validate_token_scope(activation_id)

            # Should log warning only once
            assert mock_logger.warning.call_count == 1
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "SECURITY WARNING" in warning_msg
            assert "Test Activation" in warning_msg
            assert "Legacy token without activation_instance_id" in warning_msg

    @pytest.mark.asyncio
    async def test_legacy_token_warning_includes_activation_name(
        self, mock_consumer
    ):
        """Test that warning includes the activation name."""
        from unittest.mock import AsyncMock, patch

        from channels.db import database_sync_to_async

        # Mock _get_activation_name to return the production activation name
        mock_consumer._get_activation_name = AsyncMock(
            return_value="Production Webhook Handler"
        )

        token, _ = await database_sync_to_async(create_jwt_token)()
        set_consumer_token(mock_consumer, token)

        activation_id = 456
        with patch("aap_eda.wsapi.consumers.logger") as mock_logger:
            await mock_consumer._validate_token_scope(activation_id)

            warning_msg = mock_logger.warning.call_args[0][0]
            assert "Production Webhook Handler" in warning_msg
            assert str(activation_id) in warning_msg
            assert "RECOMMENDATION: Restart activation" in warning_msg

    @pytest.mark.asyncio
    async def test_scoped_token_does_not_warn(self, mock_consumer):
        """Test that scoped tokens do not generate warnings."""
        from unittest.mock import AsyncMock, patch

        from channels.db import database_sync_to_async

        # Mock _get_activation_name (should not be called for scoped tokens)
        mock_consumer._get_activation_name = AsyncMock(
            return_value="Test Activation"
        )

        # Create scoped token
        activation_id = 789
        token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=activation_id
        )
        set_consumer_token(mock_consumer, token)

        with patch("aap_eda.wsapi.consumers.logger") as mock_logger:
            await mock_consumer._validate_token_scope(activation_id)

            # Should not log any warning for properly scoped tokens
            mock_logger.warning.assert_not_called()
            # And _get_activation_name should not be called
            mock_consumer._get_activation_name.assert_not_called()


@pytest.mark.django_db
class TestConsumerReceiveTokenValidation:
    """Tests for token validation in receive() method."""

    @pytest.mark.asyncio
    async def test_job_message_validates_token_with_ansible_rulebook_id(
        self, mock_consumer
    ):
        """Test JOB message validates token using ansible_rulebook_id.

        Regression test for security issue where JOB messages with
        ansible_rulebook_id but no activation_id would bypass token
        scope validation.
        """
        from unittest.mock import AsyncMock, patch

        from channels.db import database_sync_to_async

        # Create scoped token for activation instance 123
        activation_id = 123
        token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=activation_id
        )
        set_consumer_token(mock_consumer, token)

        # Mock the close method and _set_log_tracking_id
        mock_consumer.close = AsyncMock()
        mock_consumer._set_log_tracking_id = AsyncMock()

        # Mock the message handler to avoid database calls
        with patch.object(
            mock_consumer, "handle_jobs", new_callable=AsyncMock
        ) as mock_handle_jobs:
            # Should not raise - token validation should pass
            await mock_consumer.receive(
                text_data='{"type": "Job", "ansible_rulebook_id": 123, '
                '"job_id": "test-job-123", "name": "Test Job", '
                '"action": "run_playbook", "ruleset": "test_ruleset", '
                '"hosts": "localhost", "rule": "test_rule"}'
            )

            # Verify job was processed (not rejected)
            mock_handle_jobs.assert_called_once()
            # Verify connection was NOT closed
            mock_consumer.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_job_message_rejects_mismatched_ansible_rulebook_id(
        self, mock_consumer
    ):
        """Test JOB message rejects token when ansible_rulebook_id mismatches.

        Ensures token validation is enforced for JOB messages even when
        using ansible_rulebook_id field.
        """
        from unittest.mock import AsyncMock, patch

        from channels.db import database_sync_to_async

        # Create scoped token for activation instance 123
        token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=123
        )
        set_consumer_token(mock_consumer, token)

        # Mock the close method and _set_log_tracking_id
        mock_consumer.close = AsyncMock()
        mock_consumer._set_log_tracking_id = AsyncMock()

        # Mock handle_jobs to verify it's NOT called on rejection
        with patch.object(
            mock_consumer, "handle_jobs", new_callable=AsyncMock
        ) as mock_handle_jobs:
            # Create JOB message with mismatched ansible_rulebook_id
            # Token is scoped to 123 but message uses 456
            await mock_consumer.receive(
                text_data='{"type": "Job", "ansible_rulebook_id": 456, '
                '"job_id": "test-job-456", "name": "Test Job", '
                '"action": "run_playbook", "ruleset": "test_ruleset", '
                '"hosts": "localhost", "rule": "test_rule"}'
            )

            # Verify message was NOT dispatched
            mock_handle_jobs.assert_not_called()
            # Verify connection was closed with auth failure code
            mock_consumer.close.assert_called_once_with(code=4003)

    @pytest.mark.asyncio
    async def test_job_message_rejects_inconsistent_ids(self, mock_consumer):
        """Test JOB messages reject inconsistent activation IDs.

        Security fix: If both activation_id and ansible_rulebook_id are
        present but different, reject the message to prevent TOCTOU
        vulnerabilities where validation uses one ID but persistence
        uses another.
        """
        from unittest.mock import AsyncMock, patch

        from channels.db import database_sync_to_async

        # Create scoped token for activation instance 123
        activation_id = 123
        token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=activation_id
        )
        set_consumer_token(mock_consumer, token)

        # Mock the close method and _set_log_tracking_id
        mock_consumer.close = AsyncMock()
        mock_consumer._set_log_tracking_id = AsyncMock()

        # Mock handle_jobs to verify it's NOT called on rejection
        with patch.object(
            mock_consumer, "handle_jobs", new_callable=AsyncMock
        ) as mock_handle_jobs:
            # Message with inconsistent IDs where activation_id is 123
            # but ansible_rulebook_id is 456
            await mock_consumer.receive(
                text_data='{"type": "Job", "activation_id": 123, '
                '"ansible_rulebook_id": 456, "job_id": "test-job-789", '
                '"name": "Test Job", "action": "run_playbook", '
                '"ruleset": "test_ruleset", "hosts": "localhost", '
                '"rule": "test_rule"}'
            )

            # Verify message was NOT dispatched
            mock_handle_jobs.assert_not_called()
            # Verify connection was closed with auth failure code
            mock_consumer.close.assert_called_once_with(code=4003)

    @pytest.mark.asyncio
    async def test_job_message_accepts_consistent_ids(self, mock_consumer):
        """Test JOB messages accept matching activation IDs.

        When both activation_id and ansible_rulebook_id are present
        and equal, the message should be accepted.
        """
        from unittest.mock import AsyncMock, patch

        from channels.db import database_sync_to_async

        # Create scoped token for activation instance 123
        activation_id = 123
        token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=activation_id
        )
        set_consumer_token(mock_consumer, token)

        # Mock the close method and _set_log_tracking_id
        mock_consumer.close = AsyncMock()
        mock_consumer._set_log_tracking_id = AsyncMock()

        # Message with matching IDs
        with patch.object(
            mock_consumer, "handle_jobs", new_callable=AsyncMock
        ) as mock_handle_jobs:
            await mock_consumer.receive(
                text_data='{"type": "Job", "activation_id": 123, '
                '"ansible_rulebook_id": 123, "job_id": "test-job-789", '
                '"name": "Test Job", "action": "run_playbook", '
                '"ruleset": "test_ruleset", "hosts": "localhost", '
                '"rule": "test_rule"}'
            )

            # Should succeed - IDs are consistent
            mock_consumer.close.assert_not_called()
            mock_handle_jobs.assert_called_once()

    @pytest.mark.asyncio
    async def test_ansible_event_validates_job_activation_scope(
        self, mock_consumer
    ):
        """Test ANSIBLE_EVENT messages validate job's activation scope.

        Security fix: ANSIBLE_EVENT has no activation_id field, so we must
        resolve the activation from the job_id and validate token scope.
        """
        from unittest.mock import AsyncMock, patch

        from channels.db import database_sync_to_async

        # Create scoped token for activation instance 123
        activation_id = 123
        token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=activation_id
        )
        set_consumer_token(mock_consumer, token)

        # Mock the close method and _set_log_tracking_id
        mock_consumer.close = AsyncMock()
        mock_consumer._set_log_tracking_id = AsyncMock()

        # Mock _get_activation_id_from_job to return matching activation
        mock_consumer._get_activation_id_from_job = AsyncMock(return_value=123)

        # Mock handle_events to verify it IS called when scope matches
        with patch.object(
            mock_consumer, "handle_events", new_callable=AsyncMock
        ) as mock_handle_events:
            await mock_consumer.receive(
                text_data='{"type": "AnsibleEvent", '
                '"event": {"job_id": "job-uuid-123", "counter": 1, '
                '"stdout": "test output", "event": "verbose"}}'
            )

            # Verify message was dispatched (scope validated successfully)
            mock_handle_events.assert_called_once()
            # Verify connection was NOT closed
            mock_consumer.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_ansible_event_rejects_wrong_activation_scope(
        self, mock_consumer
    ):
        """Test ANSIBLE_EVENT rejects when job belongs to wrong activation.

        Security test: Prevent attackers from sending ANSIBLE_EVENT messages
        for jobs belonging to other activations.
        """
        from unittest.mock import AsyncMock, patch

        from channels.db import database_sync_to_async

        # Create scoped token for activation instance 123
        token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=123
        )
        set_consumer_token(mock_consumer, token)

        # Mock the close method and _set_log_tracking_id
        mock_consumer.close = AsyncMock()
        mock_consumer._set_log_tracking_id = AsyncMock()

        # Mock _get_activation_id_from_job to return DIFFERENT activation
        # Token is scoped to 123 but job belongs to activation 456
        mock_consumer._get_activation_id_from_job = AsyncMock(return_value=456)

        # Mock handle_events to verify it's NOT called on rejection
        with patch.object(
            mock_consumer, "handle_events", new_callable=AsyncMock
        ) as mock_handle_events:
            await mock_consumer.receive(
                text_data='{"type": "AnsibleEvent", '
                '"event": {"job_id": "job-uuid-456", "counter": 1, '
                '"stdout": "test output", "event": "verbose"}}'
            )

            # Verify message was NOT dispatched
            mock_handle_events.assert_not_called()
            # Verify connection was closed with auth failure code
            mock_consumer.close.assert_called_once_with(code=4003)

    @pytest.mark.asyncio
    async def test_ansible_event_rejects_missing_job_id(self, mock_consumer):
        """Test ANSIBLE_EVENT rejects when event data missing job_id.

        Security test: Ensure ANSIBLE_EVENT messages are rejected if they
        don't contain job_id, preventing bypassing of validation.
        """
        from unittest.mock import AsyncMock, patch

        from channels.db import database_sync_to_async

        # Create scoped token
        token, _ = await database_sync_to_async(create_jwt_token)(
            activation_instance_id=123
        )
        set_consumer_token(mock_consumer, token)

        # Mock the close method and _set_log_tracking_id
        mock_consumer.close = AsyncMock()
        mock_consumer._set_log_tracking_id = AsyncMock()

        # Mock handle_events to verify it's NOT called on rejection
        with patch.object(
            mock_consumer, "handle_events", new_callable=AsyncMock
        ) as mock_handle_events:
            # Send ANSIBLE_EVENT without job_id
            await mock_consumer.receive(
                text_data='{"type": "AnsibleEvent", '
                '"event": {"counter": 1, "stdout": "test"}}'
            )

            # Verify message was NOT dispatched
            mock_handle_events.assert_not_called()
            # Verify connection was closed with auth failure code
            mock_consumer.close.assert_called_once_with(code=4003)

    @pytest.mark.asyncio
    async def test_malformed_auth_header_closes_connection(
        self, mock_consumer
    ):
        """Test malformed UTF-8 in auth header triggers failure.

        Regression test for UnicodeDecodeError not being caught.
        """
        from unittest.mock import AsyncMock, patch

        # Set malformed UTF-8 bytes in authorization header
        mock_consumer.scope["headers"] = [
            (b"authorization", b"Bearer \xff\xfe invalid-utf8")
        ]

        # Mock the close method and _set_log_tracking_id
        mock_consumer.close = AsyncMock()
        mock_consumer._set_log_tracking_id = AsyncMock()

        # Mock handle_jobs to verify it's NOT called on rejection
        with patch.object(
            mock_consumer, "handle_jobs", new_callable=AsyncMock
        ) as mock_handle_jobs:
            # Try to receive a message
            await mock_consumer.receive(
                text_data='{"type": "Job", "ansible_rulebook_id": 123, '
                '"job_id": "test-job-123", "name": "Test Job", '
                '"action": "run_playbook", "ruleset": "test_ruleset", '
                '"hosts": "localhost", "rule": "test_rule"}'
            )

            # Verify message was NOT dispatched
            mock_handle_jobs.assert_not_called()
            # Verify connection was closed with auth failure code
            mock_consumer.close.assert_called_once_with(code=4003)
