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
from typing import Optional
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

    def __init__(self, eda_credential_id: int):
        self.eda_credential_id = eda_credential_id
        self.gateway_url = settings.RESOURCE_SERVER["URL"]
        self.gateway_ssl_verify = settings.RESOURCE_SERVER.get(
            "VALIDATE_HTTPS", True
        )

        self.eda_credential = models.EdaCredential.objects.get(
            id=self.eda_credential_id
        )

    def update(self):
        """Handle creating and updating the certificate in Gateway."""
        inputs = yaml.safe_load(self.eda_credential.inputs.get_secret_value())
        existing_object = self._fetch_from_gateway()

        # If the user had a certificate and then they deleted it
        # remove it from Gateway
        if existing_object and not inputs["certificate"]:
            return self.delete()

        # If the user has not provided any certificate nothing to do
        if not inputs["certificate"]:
            return

        sha256 = hashlib.sha256(
            inputs["certificate"].encode("utf-8")
        ).hexdigest()

        if existing_object.get("sha256", "") != sha256:
            data = {
                "name": self.eda_credential.name,
                "pem_data": inputs["certificate"],
                "sha256": sha256,
                "eda_credential_id": self._get_remote_id(),
            }
            headers = self._prep_headers()
            if existing_object:
                slug = f"{SLUG}/{existing_object['id']}/"
                url = urljoin(self.gateway_url, slug)
                response = requests.patch(
                    url,
                    json=data,
                    headers=headers,
                    verify=self.gateway_ssl_verify,
                    timeout=DEFAULT_TIMEOUT,
                )
            else:
                url = urljoin(self.gateway_url, SLUG)
                response = requests.post(
                    url,
                    json=data,
                    headers=headers,
                    verify=self.gateway_ssl_verify,
                    timeout=DEFAULT_TIMEOUT,
                )

            if response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_201_CREATED,
            ]:
                LOGGER.debug("Certificate updated")
            elif response.status_code == status.HTTP_400_BAD_REQUEST:
                LOGGER.error("Update failed")
            else:
                LOGGER.error("Couldn't update certificate")

        else:
            LOGGER.debug("No changes detected")

    def delete(self, event_stream_id: Optional[int]):
        """Delete the Certificate from Gateway."""
        existing_object = self._fetch_from_gateway()
        if not existing_object:
            return

        objects = models.EventStream.objects.filter(
            eda_credential_id=self.eda_credential
        )
        if not event_stream_id:
            self._delete_from_gateway(existing_object)
        elif len(objects) == 1 and event_stream_id == objects[0].id:
            self._delete_from_gateway(existing_object)

    def _delete_from_gateway(self, existing_object: dict):
        slug = f"{SLUG}/{existing_object['id']}/"
        url = urljoin(self.gateway_url, slug)
        headers = self._prep_headers()
        response = requests.delete(
            url,
            headers=headers,
            verify=self.gateway_ssl_verify,
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code == status.HTTP_200_OK:
            LOGGER.debug("Certificate object deleted")
        if response.status_code == status.HTTP_404_NOT_FOUND:
            LOGGER.warning("Certificate object missing during delete")
        else:
            LOGGER.error(
                "Could not delete certificate object in gateway. "
                f"Error code: {response.status_code}"
            )
            LOGGER.error(f"Error message: {response.text}")
            raise GatewayAPIError

    def _fetch_from_gateway(self):
        slug = f"{SLUG}/?eda_credential_id={self._get_remote_id()}"
        url = urljoin(self.gateway_url, slug)
        headers = self._prep_headers()
        response = requests.get(
            url,
            headers=headers,
            verify=self.gateway_ssl_verify,
            timeout=DEFAULT_TIMEOUT,
        )

        if response.status_code == status.HTTP_200_OK:
            LOGGER.debug("Certificate object exists in gateway")
            data = response.json()
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
        raise GatewayAPIError

    def _get_remote_id(self) -> str:
        return f"eda_{self.eda_credential_id}"

    def _prep_headers(self) -> dict:
        token = resource_server.get_service_token()
        if token:
            return {SERVICE_TOKEN_HEADER: token}

        LOGGER.error("Cannot connect to gateway service token")
        raise MissingCredentials


@receiver(post_save, sender=models.EdaCredential)
def gw_handler(sender, instance, **kwargs):
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
