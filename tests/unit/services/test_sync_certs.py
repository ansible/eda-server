from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from rest_framework import status

from aap_eda.core import models
from aap_eda.core.exceptions import GatewayAPIError, MissingCredentialsError
from aap_eda.services.sync_certs import SyncCertificates


@pytest.fixture
def mock_eda_credential():
    credential = MagicMock(spec=models.EdaCredential)
    credential.id = 1
    credential.name = "test-credential"
    credential.inputs.get_secret_value.return_value = "certificate: test-cert"
    return credential


@pytest.fixture
def sync_certs(mock_eda_credential):
    with patch("aap_eda.core.models.EdaCredential.objects.get") as mock_get:
        mock_get.return_value = mock_eda_credential
        return SyncCertificates(eda_credential_id=1)


def test_init(sync_certs, mock_eda_credential):
    assert sync_certs.eda_credential_id == 1
    assert sync_certs.eda_credential == mock_eda_credential
    assert sync_certs.gateway_url == settings.RESOURCE_SERVER["URL"]


@patch("aap_eda.services.sync_certs.requests.patch")
@patch("aap_eda.services.sync_certs.SyncCertificates._fetch_from_gateway")
@patch("aap_eda.services.sync_certs.SyncCertificates._prep_headers")
def test_update_existing_cert(
    mock_prep_headers, mock_fetch, mock_patch, sync_certs
):
    mock_fetch.return_value = {"id": 1, "sha256": "old-hash"}
    mock_prep_headers.return_value = {"X-ANSIBLE-SERVICE-AUTH": "token"}
    mock_response = MagicMock()
    mock_response.status_code = status.HTTP_200_OK
    mock_patch.return_value = mock_response

    sync_certs.update()
    mock_patch.assert_called_once()


@patch("aap_eda.services.sync_certs.requests.post")
@patch("aap_eda.services.sync_certs.SyncCertificates._fetch_from_gateway")
@patch("aap_eda.services.sync_certs.SyncCertificates._prep_headers")
def test_update_new_cert(mock_prep_headers, mock_fetch, mock_post, sync_certs):
    mock_fetch.return_value = {}
    mock_prep_headers.return_value = {"X-ANSIBLE-SERVICE-AUTH": "token"}
    mock_response = MagicMock()
    mock_response.status_code = status.HTTP_201_CREATED
    mock_post.return_value = mock_response

    sync_certs.update()
    mock_post.assert_called_once()


@patch("aap_eda.services.sync_certs.requests.delete")
@patch("aap_eda.services.sync_certs.SyncCertificates._fetch_from_gateway")
@patch("aap_eda.services.sync_certs.SyncCertificates._prep_headers")
@patch("aap_eda.core.models.EdaCredential.objects.get")
@patch("aap_eda.core.models.EventStream.objects.filter")
def test_delete(
    mock_filter,
    mock_get,
    mock_prep_headers,
    mock_fetch,
    mock_delete,
    sync_certs,
    mock_eda_credential,
):
    mock_get.return_value = mock_eda_credential
    mock_fetch.return_value = {"id": 1}
    mock_prep_headers.return_value = {"X-ANSIBLE-SERVICE-AUTH": "token"}
    mock_response = MagicMock()
    mock_response.status_code = status.HTTP_200_OK
    mock_delete.return_value = mock_response
    mock_filter.return_value = MagicMock()
    mock_filter.return_value.__len__.return_value = 0

    sync_certs.delete()
    mock_delete.assert_called_once()


@patch("aap_eda.services.sync_certs.requests.get")
@patch("aap_eda.services.sync_certs.SyncCertificates._prep_headers")
def test_fetch_from_gateway(mock_prep_headers, mock_get, sync_certs):
    mock_prep_headers.return_value = {"X-ANSIBLE-SERVICE-AUTH": "token"}
    mock_response = MagicMock()
    mock_response.status_code = status.HTTP_200_OK
    mock_response.json.return_value = {"count": 1, "results": [{"id": 1}]}
    mock_get.return_value = mock_response

    result = sync_certs._fetch_from_gateway()
    assert result == {"id": 1}


def test_get_remote_id(sync_certs):
    assert sync_certs._get_remote_id() == "eda_1"


@patch("aap_eda.services.sync_certs.resource_server.get_service_token")
def test_prep_headers(mock_get_token, sync_certs):
    mock_get_token.return_value = "test-token"
    headers = sync_certs._prep_headers()
    assert headers == {"X-ANSIBLE-SERVICE-AUTH": "test-token"}


@patch("aap_eda.services.sync_certs.resource_server.get_service_token")
def test_prep_headers_missing_credentials(mock_get_token, sync_certs):
    mock_get_token.return_value = None
    with pytest.raises(MissingCredentialsError):
        sync_certs._prep_headers()


@patch("aap_eda.services.sync_certs.requests.patch")
@patch("aap_eda.services.sync_certs.SyncCertificates._fetch_from_gateway")
@patch("aap_eda.services.sync_certs.SyncCertificates._prep_headers")
def test_update_error_handling(
    mock_prep_headers, mock_fetch, mock_patch, sync_certs
):
    mock_fetch.return_value = {"id": 1, "sha256": "old-hash"}
    mock_prep_headers.return_value = {"X-ANSIBLE-SERVICE-AUTH": "token"}
    mock_response = MagicMock()
    mock_response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    mock_response.text = "Server error"
    mock_patch.return_value = mock_response

    with pytest.raises(GatewayAPIError):
        sync_certs.update()
