#  Copyright 2025 Red Hat, Inc.
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
"""Synchronize Certificates with Gateway."""
import hashlib
import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests
import yaml
from ansible_base.resource_registry import resource_server
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework import status

from aap_eda.core import enums, models
from aap_eda.core.exceptions import GatewayAPIError, MissingCredentials

LOGGER = logging.getLogger(__name__)
SLUG = "api/gateway/v1/ca_certificates/"
DEFAULT_TIMEOUT = 30
SERVICE_TOKEN_HEADER = "X-ANSIBLE-SERVICE-AUTH"


class SyncCertificates:
    """This class synchronizes the certificates with Gateway."""

    def __init__(self, eda_credential_id: int) -> None:
        self.eda_credential_id: int = eda_credential_id
        self.gateway_url: str = settings.RESOURCE_SERVER["URL"]
        self.gateway_ssl_verify: bool = settings.RESOURCE_SERVER.get(
            "VALIDATE_HTTPS", True
        )

        self.eda_credential: models.EdaCredential = (
            models.EdaCredential.objects.get(id=self.eda_credential_id)
        )

    def update(self) -> None:
        """Handle creating and updating the certificate in Gateway."""
        inputs = self._get_credential_inputs()
        existing_object = self._fetch_from_gateway()

        # Handle certificate deletion case
        if self._should_delete_certificate(existing_object, inputs):
            return self.delete(None)

        # Handle no certificate case
        if not self._has_certificate(inputs):
            return

        # Handle certificate update case
        if self._certificate_needs_update(existing_object, inputs):
            self._update_certificate_in_gateway(existing_object, inputs)
        else:
            LOGGER.debug("No changes detected")

    def _get_credential_inputs(self) -> Dict[str, Any]:
        """Get and parse credential inputs."""
        return yaml.safe_load(self.eda_credential.inputs.get_secret_value())

    def _should_delete_certificate(
        self, existing_object: Dict[str, Any], inputs: Dict[str, Any]
    ) -> bool:
        """Check if certificate should be deleted from Gateway."""
        return existing_object and not inputs.get("certificate")

    def _has_certificate(self, inputs: Dict[str, Any]) -> bool:
        """Check if inputs contain a certificate."""
        return bool(inputs.get("certificate"))

    def _certificate_needs_update(
        self, existing_object: Dict[str, Any], inputs: Dict[str, Any]
    ) -> bool:
        """Check if certificate needs to be updated in Gateway."""
        certificate = inputs["certificate"]
        current_sha256 = hashlib.sha256(
            certificate.encode("utf-8")
        ).hexdigest()
        existing_sha256 = existing_object.get("sha256", "")
        return existing_sha256 != current_sha256

    def _update_certificate_in_gateway(
        self, existing_object: Dict[str, Any], inputs: Dict[str, Any]
    ) -> None:
        """Update or create certificate in Gateway."""
        certificate = inputs["certificate"]
        sha256 = hashlib.sha256(certificate.encode("utf-8")).hexdigest()

        data = {
            "name": self.eda_credential.name,
            "pem_data": certificate,
            "sha256": sha256,
            "related_id_reference": self._get_remote_id(),
        }

        if existing_object:
            response = self._patch_certificate(existing_object["id"], data)
        else:
            response = self._post_certificate(data)

        self._handle_certificate_response(response)

    def _patch_certificate(
        self, cert_id: str, data: Dict[str, str]
    ) -> requests.Response:
        """Update existing certificate in Gateway."""
        slug = f"{SLUG}/{cert_id}/"
        url = urljoin(self.gateway_url, slug)
        return self._make_request("patch", url, data)

    def _post_certificate(self, data: Dict[str, str]) -> requests.Response:
        """Create new certificate in Gateway."""
        url = urljoin(self.gateway_url, SLUG)
        return self._make_request("post", url, data)

    def _make_request(
        self, method: str, url: str, data: Dict[str, str]
    ) -> requests.Response:
        """Make HTTP request with proper error handling."""
        headers = self._prep_headers()

        try:
            response = getattr(requests, method)(
                url,
                json=data,
                headers=headers,
                verify=self.gateway_ssl_verify,
                timeout=DEFAULT_TIMEOUT,
            )
            return response
        except requests.exceptions.ConnectionError as ex:
            LOGGER.error(
                "Connection error while updating certificate: %s", str(ex)
            )
            raise GatewayAPIError(f"Connection error: {str(ex)}")
        except requests.exceptions.Timeout as ex:
            LOGGER.error("Timeout while updating certificate: %s", str(ex))
            raise GatewayAPIError(f"Request timeout: {str(ex)}")
        except requests.exceptions.RequestException as ex:
            LOGGER.error(
                "Request error while updating certificate: %s", str(ex)
            )
            raise GatewayAPIError(f"Request error: {str(ex)}")

    def _handle_certificate_response(
        self, response: requests.Response
    ) -> None:
        """Handle response from certificate update/create operation."""
        if response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
        ]:
            LOGGER.debug("Certificate updated")
        elif response.status_code == status.HTTP_400_BAD_REQUEST:
            LOGGER.error("Update failed")
            raise GatewayAPIError(response.text)
        else:
            LOGGER.error("Couldn't update certificate")
            raise GatewayAPIError(response.text)

    def delete(self, event_stream_id: Optional[int]) -> None:
        """Delete the Certificate from Gateway."""
        existing_object: Dict[str, Any] = self._fetch_from_gateway()
        if not existing_object:
            return

        objects = models.EventStream.objects.filter(
            eda_credential_id=self.eda_credential_id
        )

        if not event_stream_id or (
            len(objects) == 1 and event_stream_id == objects[0].id
        ):
            self._delete_from_gateway(existing_object)

    def _delete_from_gateway(self, existing_object: Dict[str, Any]) -> None:
        slug: str = f"{SLUG}/{existing_object['id']}/"
        url: str = urljoin(self.gateway_url, slug)
        headers: Dict[str, str] = self._prep_headers()

        try:
            response: requests.Response = requests.delete(
                url,
                headers=headers,
                verify=self.gateway_ssl_verify,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.exceptions.ConnectionError as ex:
            LOGGER.error(
                "Connection error while deleting certificate: %s", str(ex)
            )
            raise GatewayAPIError(f"Connection error: {str(ex)}")
        except requests.exceptions.Timeout as ex:
            LOGGER.error("Timeout while deleting certificate: %s", str(ex))
            raise GatewayAPIError(f"Request timeout: {str(ex)}")
        except requests.exceptions.RequestException as ex:
            LOGGER.error(
                "Request error while deleting certificate: %s", str(ex)
            )
            raise GatewayAPIError(f"Request error: {str(ex)}")

        if response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
        ]:
            LOGGER.debug("Certificate object deleted")
        elif response.status_code == status.HTTP_404_NOT_FOUND:
            LOGGER.warning("Certificate object missing during delete")
        else:
            LOGGER.error(
                "Could not delete certificate object in gateway. "
                f"Error code: {response.status_code}"
            )
            LOGGER.error(f"Error message: {response.text}")
            raise GatewayAPIError(response.text)

    def _fetch_from_gateway(self) -> Dict[str, Any]:
        slug: str = f"{SLUG}/?related_id_reference={self._get_remote_id()}"
        url: str = urljoin(self.gateway_url, slug)
        headers: Dict[str, str] = self._prep_headers()

        try:
            response: requests.Response = requests.get(
                url,
                headers=headers,
                verify=self.gateway_ssl_verify,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.exceptions.ConnectionError as ex:
            LOGGER.error(
                "Connection error while fetching certificate: %s", str(ex)
            )
            raise GatewayAPIError(f"Connection error: {str(ex)}")
        except requests.exceptions.Timeout as ex:
            LOGGER.error("Timeout while fetching certificate: %s", str(ex))
            raise GatewayAPIError(f"Request timeout: {str(ex)}")
        except requests.exceptions.RequestException as ex:
            LOGGER.error(
                "Request error while fetching certificate: %s", str(ex)
            )
            raise GatewayAPIError(f"Request error: {str(ex)}")

        if response.status_code == status.HTTP_200_OK:
            LOGGER.debug("Certificate object exists in gateway")
            data: Dict[str, Any] = response.json()
            if data["count"] > 0:
                return data["results"][0]
            else:
                return {}
        if response.status_code == status.HTTP_404_NOT_FOUND:
            LOGGER.debug("Certificate object does not exist in gateway")
            return {}

        LOGGER.error(
            "Error fetching certificate object. "
            f"Error code: {response.status_code}"
        )
        LOGGER.error(f"Error message: {response.text}")
        raise GatewayAPIError(response.text)

    def _get_remote_id(self) -> str:
        return f"eda_{self.eda_credential_id}"

    def _prep_headers(self) -> Dict[str, str]:
        token: Optional[str] = resource_server.get_service_token()
        if token:
            return {SERVICE_TOKEN_HEADER: token}

        LOGGER.error("Cannot connect to gateway service token")
        raise MissingCredentials


@receiver(post_save, sender=models.EdaCredential)
def gw_handler(
    sender: Any, instance: models.EdaCredential, **kwargs: Any
) -> None:
    """Handle updates to EdaCredential object and force a certificate sync."""
    if (
        instance.credential_type is not None
        and instance.credential_type.name
        == enums.EventStreamCredentialType.MTLS
        and hasattr(instance, "_request")
    ):
        try:
            objects = models.EventStream.objects.filter(
                eda_credential_id=instance.id
            )
            if len(objects) > 0:
                SyncCertificates(instance.id).update()
        except (GatewayAPIError, MissingCredentials) as ex:
            LOGGER.error(
                "Couldn't trigger gateway certificate updates %s", str(ex)
            )
