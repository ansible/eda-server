"""Unit tests for certificate synchronization service."""
import hashlib
from unittest.mock import Mock, patch

import pytest
import requests
from rest_framework import status

from aap_eda.core import enums, models
from aap_eda.core.exceptions import GatewayAPIError, MissingCredentials
from aap_eda.core.utils.credentials import inputs_to_store
from aap_eda.services.sync_certs import SyncCertificates, gw_handler


@pytest.fixture
def mock_settings():
    """Mock Django settings for testing."""
    with patch("aap_eda.services.sync_certs.settings") as mock:
        mock.RESOURCE_SERVER = {
            "URL": "https://gateway.example.com",
            "VALIDATE_HTTPS": True,
        }
        yield mock


@pytest.fixture
def mtls_credential_type(preseed_credential_types):
    """Get the real mTLS credential type."""
    return models.CredentialType.objects.get(
        name=enums.EventStreamCredentialType.MTLS
    )


@pytest.fixture
def default_mtls_credential(
    default_organization: models.Organization,
    mtls_credential_type: models.CredentialType,
):
    """Create a real EDA credential with mTLS type."""
    cert_data = (
        "-----BEGIN CERTIFICATE-----\n"
        "MIICert...\n"
        "-----END CERTIFICATE-----"
    )
    return models.EdaCredential.objects.create(
        name="test-credential",
        description="Test mTLS Credential",
        credential_type=mtls_credential_type,
        inputs=inputs_to_store({"certificate": cert_data}),
        organization=default_organization,
    )


@pytest.fixture
def empty_mtls_credential(
    default_organization: models.Organization,
    mtls_credential_type: models.CredentialType,
):
    """Create a real EDA credential with empty certificate."""
    return models.EdaCredential.objects.create(
        name="test-credential",
        description="Test mTLS Credential",
        credential_type=mtls_credential_type,
        inputs=inputs_to_store({"certificate": ""}),
        organization=default_organization,
    )


@pytest.fixture
def mock_service_token():
    """Mock the resource server service token."""
    with patch("aap_eda.services.sync_certs.resource_server") as mock:
        mock.get_service_token.return_value = "mock-token"
        yield mock


# SyncCertificates tests


@pytest.mark.django_db
def test_sync_certificates_init(mock_settings, default_mtls_credential):
    """Test SyncCertificates initialization."""
    sync = SyncCertificates(default_mtls_credential.id)

    assert sync.eda_credential_id == default_mtls_credential.id
    assert sync.gateway_url == "https://gateway.example.com"
    assert sync.gateway_ssl_verify is True
    assert sync.eda_credential == default_mtls_credential


@pytest.mark.django_db
def test_sync_certificates_init_ssl_verify_false(default_mtls_credential):
    """Test SyncCertificates init with SSL verification disabled."""
    with patch("aap_eda.services.sync_certs.settings") as mock_settings:
        mock_settings.RESOURCE_SERVER = {
            "URL": "https://gateway.example.com",
            "VALIDATE_HTTPS": False,
        }

        sync = SyncCertificates(default_mtls_credential.id)
        assert sync.gateway_ssl_verify is False


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.post")
def test_update_creates_new_certificate(
    mock_post,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test creating a new certificate in Gateway."""
    mock_post.return_value.status_code = status.HTTP_201_CREATED

    sync = SyncCertificates(default_mtls_credential.id)

    with patch.object(sync, "_fetch_from_gateway", return_value={}):
        sync.update()

    # Verify the POST request was made with correct data
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args

    assert (
        "https://gateway.example.com/api/gateway/v1/ca_certificates/"
        in args[0]
    )
    assert kwargs["json"]["name"] == "test-credential"
    assert "-----BEGIN CERTIFICATE-----" in kwargs["json"]["pem_data"]
    assert "sha256" in kwargs["json"]
    assert (
        kwargs["json"]["related_id_reference"]
        == f"eda_{default_mtls_credential.id}"
    )
    assert kwargs["headers"]["X-ANSIBLE-SERVICE-AUTH"] == "mock-token"
    assert kwargs["verify"] is True
    assert kwargs["timeout"] == 30


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.patch")
def test_update_modifies_existing_certificate(
    mock_patch,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test updating an existing certificate in Gateway."""
    mock_patch.return_value.status_code = status.HTTP_200_OK

    existing_object = {"id": 123, "sha256": "different-hash"}

    sync = SyncCertificates(default_mtls_credential.id)

    with patch.object(
        sync, "_fetch_from_gateway", return_value=existing_object
    ):
        sync.update()

    mock_patch.assert_called_once()
    args, _ = mock_patch.call_args
    assert "/123/" in args[0]


@pytest.mark.django_db
def test_update_no_changes_detected(
    mock_settings, default_mtls_credential, mock_service_token
):
    """Test no update when certificate hasn't changed."""
    # Calculate the expected SHA256
    cert_data = (
        "-----BEGIN CERTIFICATE-----\n"
        "MIICert...\n"
        "-----END CERTIFICATE-----"
    )
    expected_sha256 = hashlib.sha256(cert_data.encode("utf-8")).hexdigest()

    existing_object = {"id": 123, "sha256": expected_sha256}

    sync = SyncCertificates(default_mtls_credential.id)

    with patch.object(
        sync, "_fetch_from_gateway", return_value=existing_object
    ):
        with patch("aap_eda.services.sync_certs.requests") as mock_requests:
            sync.update()

            # No HTTP requests should be made
            mock_requests.post.assert_not_called()
            mock_requests.patch.assert_not_called()


@pytest.mark.django_db
def test_update_deletes_when_certificate_removed(
    mock_settings, empty_mtls_credential
):
    """Test deleting certificate when user removes it."""
    existing_object = {"id": 123}

    sync = SyncCertificates(empty_mtls_credential.id)

    with patch.object(
        sync, "_fetch_from_gateway", return_value=existing_object
    ):
        with patch.object(sync, "delete") as mock_delete:
            sync.update()
            mock_delete.assert_called_once()


@pytest.mark.django_db
def test_update_no_action_when_no_certificate(
    mock_settings, empty_mtls_credential
):
    """Test no action when no certificate is provided."""
    sync = SyncCertificates(empty_mtls_credential.id)

    with patch.object(sync, "_fetch_from_gateway", return_value={}):
        with patch("aap_eda.services.sync_certs.requests") as mock_requests:
            sync.update()

            mock_requests.post.assert_not_called()
            mock_requests.patch.assert_not_called()


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.post")
def test_update_handles_bad_request_error(
    mock_post,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test handling of 400 Bad Request error."""
    mock_post.return_value.status_code = status.HTTP_400_BAD_REQUEST
    mock_post.return_value.text = "Invalid certificate data"

    sync = SyncCertificates(default_mtls_credential.id)

    with patch.object(sync, "_fetch_from_gateway", return_value={}):
        with pytest.raises(GatewayAPIError, match="Invalid certificate data"):
            sync.update()


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.post")
def test_update_handles_other_errors(
    mock_post,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test handling of other HTTP errors."""
    mock_post.return_value.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    mock_post.return_value.text = "Internal server error"

    sync = SyncCertificates(default_mtls_credential.id)

    with patch.object(sync, "_fetch_from_gateway", return_value={}):
        with pytest.raises(GatewayAPIError, match="Internal server error"):
            sync.update()


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.models.EventStream.objects.filter")
@patch("aap_eda.services.sync_certs.requests.delete")
def test_delete_removes_certificate(
    mock_delete,
    mock_filter,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test deleting certificate from Gateway."""
    mock_delete.return_value.status_code = status.HTTP_204_NO_CONTENT

    existing_object = {"id": 123}

    sync = SyncCertificates(default_mtls_credential.id)

    with patch.object(
        sync, "_fetch_from_gateway", return_value=existing_object
    ):
        sync.delete(None)

    mock_delete.assert_called_once()
    args, _ = mock_delete.call_args
    assert "/123/" in args[0]


@pytest.mark.django_db
def test_delete_no_existing_object(mock_settings, default_mtls_credential):
    """Test delete when no object exists in Gateway."""
    sync = SyncCertificates(default_mtls_credential.id)

    with patch.object(sync, "_fetch_from_gateway", return_value={}):
        with patch("aap_eda.services.sync_certs.requests") as mock_requests:
            sync.delete(None)
            mock_requests.delete.assert_not_called()


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.models.EventStream.objects.filter")
def test_delete_with_event_stream_id_single_match(
    mock_filter, mock_settings, default_mtls_credential
):
    """Test delete when event_stream_id matches single object."""
    # Mock single EventStream object
    event_stream = Mock()
    event_stream.id = 456
    mock_filter.return_value = [event_stream]

    existing_object = {"id": 123}

    sync = SyncCertificates(default_mtls_credential.id)

    with patch.object(
        sync, "_fetch_from_gateway", return_value=existing_object
    ):
        with patch.object(sync, "_delete_from_gateway") as mock_delete_gateway:
            sync.delete(456)  # Same ID as the event stream
            mock_delete_gateway.assert_called_once_with(existing_object)


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.models.EventStream.objects.filter")
def test_delete_with_event_stream_id_no_match(
    mock_filter, mock_settings, default_mtls_credential
):
    """Test delete when event_stream_id doesn't match."""
    # Mock single EventStream object with different ID
    event_stream = Mock()
    event_stream.id = 456
    mock_filter.return_value = [event_stream]

    existing_object = {"id": 123}

    sync = SyncCertificates(default_mtls_credential.id)

    with patch.object(
        sync, "_fetch_from_gateway", return_value=existing_object
    ):
        with patch.object(sync, "_delete_from_gateway") as mock_delete_gateway:
            sync.delete(999)  # Different ID
            mock_delete_gateway.assert_not_called()


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.delete")
def test_delete_from_gateway_success(
    mock_delete,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test successful deletion from Gateway."""
    mock_delete.return_value.status_code = status.HTTP_204_NO_CONTENT

    sync = SyncCertificates(default_mtls_credential.id)
    existing_object = {"id": 123}

    sync._delete_from_gateway(existing_object)

    mock_delete.assert_called_once()


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.delete")
def test_delete_from_gateway_not_found(
    mock_delete,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test deletion when object not found (warning case)."""
    mock_delete.return_value.status_code = status.HTTP_404_NOT_FOUND

    sync = SyncCertificates(default_mtls_credential.id)
    existing_object = {"id": 123}

    # Should not raise exception, just log warning
    sync._delete_from_gateway(existing_object)


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.delete")
def test_delete_from_gateway_error(
    mock_delete,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test deletion error handling."""
    mock_delete.return_value.status_code = (
        status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    mock_delete.return_value.text = "Server error"

    sync = SyncCertificates(default_mtls_credential.id)
    existing_object = {"id": 123}

    with pytest.raises(GatewayAPIError, match="Server error"):
        sync._delete_from_gateway(existing_object)


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.get")
def test_fetch_from_gateway_exists(
    mock_get_request,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test fetching existing certificate from Gateway."""
    response_data = {
        "count": 1,
        "results": [{"id": 123, "sha256": "abc123"}],
    }
    mock_get_request.return_value.status_code = status.HTTP_200_OK
    mock_get_request.return_value.json.return_value = response_data

    sync = SyncCertificates(default_mtls_credential.id)
    result = sync._fetch_from_gateway()

    assert result == {"id": 123, "sha256": "abc123"}
    mock_get_request.assert_called_once()


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.get")
def test_fetch_from_gateway_not_found(
    mock_get_request,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test fetching when certificate doesn't exist."""
    mock_get_request.return_value.status_code = status.HTTP_404_NOT_FOUND

    sync = SyncCertificates(default_mtls_credential.id)
    result = sync._fetch_from_gateway()

    assert result == {}


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.get")
def test_fetch_from_gateway_empty_results(
    mock_get_request,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test fetching when no results returned."""
    response_data = {"count": 0, "results": []}
    mock_get_request.return_value.status_code = status.HTTP_200_OK
    mock_get_request.return_value.json.return_value = response_data

    sync = SyncCertificates(default_mtls_credential.id)
    result = sync._fetch_from_gateway()

    assert result == {}


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.get")
def test_fetch_from_gateway_error(
    mock_get_request,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test error handling in fetch_from_gateway."""
    mock_get_request.return_value.status_code = (
        status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    mock_get_request.return_value.text = "Server error"

    sync = SyncCertificates(default_mtls_credential.id)

    with pytest.raises(GatewayAPIError, match="Server error"):
        sync._fetch_from_gateway()


@pytest.mark.django_db
def test_get_remote_id(mock_settings, default_mtls_credential):
    """Test remote ID generation."""
    sync = SyncCertificates(default_mtls_credential.id)
    remote_id = sync._get_remote_id()

    assert remote_id == f"eda_{default_mtls_credential.id}"


@pytest.mark.django_db
def test_prep_headers_with_token(
    mock_settings, default_mtls_credential, mock_service_token
):
    """Test header preparation with valid token."""
    sync = SyncCertificates(default_mtls_credential.id)
    headers = sync._prep_headers()

    assert headers == {"X-ANSIBLE-SERVICE-AUTH": "mock-token"}


@pytest.mark.django_db
def test_prep_headers_no_token(mock_settings, default_mtls_credential):
    """Test header preparation when no token available."""
    with patch("aap_eda.services.sync_certs.resource_server") as mock_rs:
        mock_rs.get_service_token.return_value = None

        sync = SyncCertificates(default_mtls_credential.id)

        with pytest.raises(MissingCredentials):
            sync._prep_headers()


# Signal handler tests


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.models.EventStream.objects.filter")
@patch("aap_eda.services.sync_certs.SyncCertificates")
def test_gw_handler_triggers_sync(
    mock_sync_class, mock_filter, mtls_credential_type
):
    """Test signal handler triggers certificate sync."""
    # Create mock instance
    instance = Mock()
    instance.id = 1
    instance.credential_type = mtls_credential_type
    instance._request = Mock()  # Simulate having _request attribute

    # Mock EventStream objects
    event_stream = Mock()
    mock_filter.return_value = [event_stream]

    # Mock SyncCertificates instance
    mock_sync_instance = Mock()
    mock_sync_class.return_value = mock_sync_instance

    # Call the signal handler
    gw_handler(models.EdaCredential, instance)

    # Verify sync was triggered
    mock_sync_class.assert_called_once_with(1)
    mock_sync_instance.update.assert_called_once()


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.models.EventStream.objects.filter")
@patch("aap_eda.services.sync_certs.SyncCertificates")
def test_gw_handler_no_event_streams(
    mock_sync_class, mock_filter, mtls_credential_type
):
    """Test signal handler when no EventStreams exist."""
    instance = Mock()
    instance.id = 1
    instance.credential_type = mtls_credential_type
    instance._request = Mock()

    # No EventStreams
    mock_filter.return_value = []

    gw_handler(models.EdaCredential, instance)

    # Should not trigger sync
    mock_sync_class.assert_not_called()


@patch("aap_eda.services.sync_certs.models.EventStream.objects.filter")
@patch("aap_eda.services.sync_certs.SyncCertificates")
def test_gw_handler_wrong_credential_type(mock_sync_class, mock_filter):
    """Test signal handler with wrong credential type."""
    instance = Mock()
    instance.id = 1

    # Wrong credential type
    wrong_type = Mock()
    wrong_type.name = "wrong_type"
    instance.credential_type = wrong_type
    instance._request = Mock()

    gw_handler(models.EdaCredential, instance)

    # Should not trigger sync
    mock_sync_class.assert_not_called()


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.models.EventStream.objects.filter")
@patch("aap_eda.services.sync_certs.SyncCertificates")
def test_gw_handler_no_request_attribute(
    mock_sync_class, mock_filter, mtls_credential_type
):
    """Test signal handler when _request attribute is missing."""
    instance = Mock()
    instance.id = 1
    instance.credential_type = mtls_credential_type
    # No _request attribute
    if hasattr(instance, "_request"):
        delattr(instance, "_request")

    gw_handler(models.EdaCredential, instance)

    # Should not trigger sync
    mock_sync_class.assert_not_called()


def test_gw_handler_no_credential_type():
    """Test signal handler when credential_type is None."""
    instance = Mock()
    instance.id = 1
    instance.credential_type = None

    with patch(
        "aap_eda.services.sync_certs.SyncCertificates"
    ) as mock_sync_class:
        gw_handler(models.EdaCredential, instance)
        mock_sync_class.assert_not_called()


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.models.EventStream.objects.filter")
@patch("aap_eda.services.sync_certs.SyncCertificates")
def test_gw_handler_handles_gateway_api_error(
    mock_sync_class, mock_filter, mtls_credential_type
):
    """Test signal handler handles GatewayAPIError gracefully."""
    instance = Mock()
    instance.id = 1
    instance.credential_type = mtls_credential_type
    instance._request = Mock()

    # Mock EventStream objects
    event_stream = Mock()
    mock_filter.return_value = [event_stream]

    # Mock SyncCertificates to raise GatewayAPIError
    mock_sync_instance = Mock()
    mock_sync_instance.update.side_effect = GatewayAPIError("API Error")
    mock_sync_class.return_value = mock_sync_instance

    # Should not raise exception
    gw_handler(models.EdaCredential, instance)


@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.models.EventStream.objects.filter")
@patch("aap_eda.services.sync_certs.SyncCertificates")
def test_gw_handler_handles_missing_credentials(
    mock_sync_class, mock_filter, mtls_credential_type
):
    """Test signal handler handles MissingCredentials gracefully."""
    instance = Mock()
    instance.id = 1
    instance.credential_type = mtls_credential_type
    instance._request = Mock()

    # Mock EventStream objects
    event_stream = Mock()
    mock_filter.return_value = [event_stream]

    # Mock SyncCertificates to raise MissingCredentials
    mock_sync_instance = Mock()
    mock_sync_instance.update.side_effect = MissingCredentials(
        "No credentials"
    )
    mock_sync_class.return_value = mock_sync_instance

    # Should not raise exception
    gw_handler(models.EdaCredential, instance)


# Parameterized tests


@pytest.mark.parametrize(
    "status_code,should_raise",
    [
        (status.HTTP_200_OK, False),
        (status.HTTP_201_CREATED, False),
        (status.HTTP_400_BAD_REQUEST, True),
        (status.HTTP_500_INTERNAL_SERVER_ERROR, True),
    ],
)
@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.post")
def test_update_response_codes(
    mock_post,
    status_code,
    should_raise,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test various HTTP response codes in update method."""
    mock_post.return_value.status_code = status_code
    mock_post.return_value.text = "Error message"

    sync = SyncCertificates(default_mtls_credential.id)

    with patch.object(sync, "_fetch_from_gateway", return_value={}):
        if should_raise:
            with pytest.raises(GatewayAPIError):
                sync.update()
        else:
            sync.update()  # Should not raise


@pytest.mark.parametrize(
    "status_code,should_raise",
    [
        (status.HTTP_200_OK, False),
        (status.HTTP_204_NO_CONTENT, False),
        (status.HTTP_404_NOT_FOUND, False),  # Warning case
        (status.HTTP_500_INTERNAL_SERVER_ERROR, True),
    ],
)
@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.delete")
def test_delete_response_codes(
    mock_delete,
    status_code,
    should_raise,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test various HTTP response codes in delete method."""
    mock_delete.return_value.status_code = status_code
    mock_delete.return_value.text = "Error message"

    sync = SyncCertificates(default_mtls_credential.id)
    existing_object = {"id": 123}

    if should_raise:
        with pytest.raises(GatewayAPIError):
            sync._delete_from_gateway(existing_object)
    else:
        sync._delete_from_gateway(existing_object)  # Should not raise


@pytest.mark.parametrize(
    "status_code,should_raise",
    [
        (status.HTTP_200_OK, False),
        (status.HTTP_404_NOT_FOUND, False),
        (status.HTTP_500_INTERNAL_SERVER_ERROR, True),
    ],
)
@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.get")
def test_fetch_response_codes(
    mock_get_request,
    status_code,
    should_raise,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test various HTTP response codes in fetch method."""
    mock_get_request.return_value.status_code = status_code
    mock_get_request.return_value.text = "Error message"
    mock_get_request.return_value.json.return_value = {
        "count": 0,
        "results": [],
    }

    sync = SyncCertificates(default_mtls_credential.id)

    if should_raise:
        with pytest.raises(GatewayAPIError):
            sync._fetch_from_gateway()
    else:
        result = sync._fetch_from_gateway()
        assert result == {}


# Exception handling tests for new network error scenarios


@pytest.mark.parametrize(
    "request_method,exception_class,error_message,expected_prefix,"
    "existing_object",
    [
        # POST requests (new certificates)
        (
            "post",
            requests.exceptions.ConnectionError,
            "Connection refused",
            "Connection error",
            {},
        ),
        (
            "post",
            requests.exceptions.Timeout,
            "Request timed out",
            "Request timeout",
            {},
        ),
        (
            "post",
            requests.exceptions.RequestException,
            "Generic request error",
            "Request error",
            {},
        ),
        # PATCH requests (updating existing certificates)
        (
            "patch",
            requests.exceptions.ConnectionError,
            "Network unreachable",
            "Connection error",
            {"id": 123, "sha256": "different-hash"},
        ),
        (
            "patch",
            requests.exceptions.Timeout,
            "Read timeout occurred",
            "Request timeout",
            {"id": 123, "sha256": "different-hash"},
        ),
        (
            "patch",
            requests.exceptions.RequestException,
            "SSL certificate error",
            "Request error",
            {"id": 123, "sha256": "different-hash"},
        ),
    ],
)
@pytest.mark.django_db
def test_update_handles_network_exceptions(
    request_method,
    exception_class,
    error_message,
    expected_prefix,
    existing_object,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test handling of network exceptions during update() method."""
    sync = SyncCertificates(default_mtls_credential.id)

    with patch.object(
        sync, "_fetch_from_gateway", return_value=existing_object
    ):
        with patch(
            f"aap_eda.services.sync_certs.requests.{request_method}"
        ) as mock_request:
            mock_request.side_effect = exception_class(error_message)

            with pytest.raises(
                GatewayAPIError, match=f"{expected_prefix}: {error_message}"
            ):
                sync.update()


@pytest.mark.parametrize(
    "exception_class,error_message,expected_prefix",
    [
        (
            requests.exceptions.ConnectionError,
            "Connection refused",
            "Connection error",
        ),
        (
            requests.exceptions.Timeout,
            "Delete timed out",
            "Request timeout",
        ),
        (
            requests.exceptions.RequestException,
            "HTTP adapter error",
            "Request error",
        ),
    ],
)
@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.delete")
def test_delete_from_gateway_handles_network_exceptions(
    mock_delete,
    exception_class,
    error_message,
    expected_prefix,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test handling of network exceptions in _delete_from_gateway()."""
    mock_delete.side_effect = exception_class(error_message)

    sync = SyncCertificates(default_mtls_credential.id)
    existing_object = {"id": 123}

    with pytest.raises(
        GatewayAPIError, match=f"{expected_prefix}: {error_message}"
    ):
        sync._delete_from_gateway(existing_object)


@pytest.mark.parametrize(
    "exception_class,error_message,expected_prefix",
    [
        (
            requests.exceptions.ConnectionError,
            "Connection refused",
            "Connection error",
        ),
        (
            requests.exceptions.Timeout,
            "Fetch timed out",
            "Request timeout",
        ),
        (
            requests.exceptions.RequestException,
            "DNS resolution failed",
            "Request error",
        ),
    ],
)
@pytest.mark.django_db
@patch("aap_eda.services.sync_certs.requests.get")
def test_fetch_from_gateway_handles_network_exceptions(
    mock_get_request,
    exception_class,
    error_message,
    expected_prefix,
    mock_settings,
    default_mtls_credential,
    mock_service_token,
):
    """Test handling of network exceptions in _fetch_from_gateway()."""
    mock_get_request.side_effect = exception_class(error_message)

    sync = SyncCertificates(default_mtls_credential.id)

    with pytest.raises(
        GatewayAPIError, match=f"{expected_prefix}: {error_message}"
    ):
        sync._fetch_from_gateway()
