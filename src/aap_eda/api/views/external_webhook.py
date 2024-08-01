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
"""Module providing external webhook post."""

import datetime
import logging
import urllib.parse

import yaml
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.http.request import HttpHeaders
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, ParseError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from aap_eda.api.webhook_authentication import (
    BasicAuthentication,
    EcdsaAuthentication,
    HMACAuthentication,
    MTLSAuthentication,
    Oauth2Authentication,
    Oauth2JwtAuthentication,
    TokenAuthentication,
)
from aap_eda.core.enums import Action, ResourceType, WebhookAuthType
from aap_eda.core.exceptions import PGNotifyError
from aap_eda.core.models import Webhook
from aap_eda.services.pg_notify import PGNotify

logger = logging.getLogger(__name__)


class ExternalWebhookViewSet(viewsets.GenericViewSet):
    """External Webhook View Set."""

    rbac_action = None
    rbac_resource_type = ResourceType.WEBHOOK
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_rbac_permission(self):
        """RBAC Permissions."""
        return ResourceType.WEBHOOK, Action.READ

    def __init__(self, *args, **kwargs):
        self.webhook = None
        super().__init__()

    def _update_test_data(
        self,
        error_message: str = "",
        content_type: str = "",
        content: str = "",
        headers: str = "",
    ):
        logger.warning(
            "The webhook: %s is currently in test mode", self.webhook.name
        )
        self.webhook.test_error_message = error_message
        self.webhook.test_content_type = content_type
        self.webhook.test_content = content
        self.webhook.test_headers = headers
        self.webhook.save(
            update_fields=[
                "test_content_type",
                "test_content",
                "test_headers",
                "test_error_message",
            ]
        )

    def _parse_body(self, content_type: str, body: bytes) -> dict:
        if content_type == "application/json":
            data = yaml.safe_load(body.decode())
        elif content_type == "application/x-www-form-urlencoded":
            data = urllib.parse.parse_qs(body.decode())
        else:
            try:
                data = yaml.safe_load(body.decode())
            except yaml.YAMLError as exc:
                message = f"Invalid content type passed {content_type}"
                logger.error(message)
                raise ParseError(message) from exc
        return data

    def _create_payload(
        self, headers: HttpHeaders, data: dict, header_key: str, endpoint: str
    ) -> dict:
        event_headers = {}
        if self.webhook.additional_data_headers:
            for key in self.webhook.additional_data_headers.split(","):
                value = headers.get(key)
                if value:
                    event_headers[key] = value
        else:
            event_headers = dict(headers)
            if header_key in event_headers:
                event_headers.pop(header_key)

        return {
            "payload": data,
            "meta": {
                "endpoint": endpoint,
                "eda_webhook_name": self.webhook.name,
                "headers": event_headers,
            },
        }

    @transaction.atomic
    def _update_stats(self):
        self.webhook.events_received = F("events_received") + 1
        self.webhook.last_event_received_at = datetime.datetime.now(
            tz=datetime.timezone.utc
        )
        self.webhook.save(
            update_fields=[
                "events_received",
                "last_event_received_at",
            ]
        )

    def _handle_auth(self, request, inputs):
        try:
            if inputs["auth_type"] == WebhookAuthType.HMAC:
                obj = HMACAuthentication(
                    signature_encoding=inputs["signature_encoding"],
                    signature_prefix=inputs.get("signature_prefix", ""),
                    signature=request.headers[inputs["http_header_key"]],
                    hash_algorithm=inputs["hash_algorithm"],
                    secret=inputs["secret"].encode("utf-8"),
                )
                obj.authenticate(request.body)
            elif inputs["auth_type"] == WebhookAuthType.MTLS:
                obj = MTLSAuthentication(
                    subject=inputs.get("subject", ""),
                    value=request.headers[inputs["http_header_key"]],
                )
                obj.authenticate()
            elif inputs["auth_type"] == WebhookAuthType.TOKEN:
                obj = TokenAuthentication(
                    token=inputs["token"],
                    value=request.headers[inputs["http_header_key"]],
                )
                obj.authenticate()
            elif inputs["auth_type"] == WebhookAuthType.BASIC:
                obj = BasicAuthentication(
                    password=inputs["password"],
                    username=inputs["username"],
                    authorization=request.headers[inputs["http_header_key"]],
                )
                obj.authenticate()
            elif inputs["auth_type"] == WebhookAuthType.OAUTH2JWT:
                obj = Oauth2JwtAuthentication(
                    jwks_url=inputs["jwks_url"],
                    audience=inputs["audience"],
                    access_token=request.headers[inputs["http_header_key"]],
                )
                obj.authenticate()
            elif inputs["auth_type"] == WebhookAuthType.OAUTH2:
                obj = Oauth2Authentication(
                    introspection_url=inputs["introspection_url"],
                    token=request.headers[inputs["http_header_key"]],
                    client_id=inputs["client_id"],
                    client_secret=inputs["client_secret"],
                )
                obj.authenticate()
            elif inputs["auth_type"] == WebhookAuthType.ECDSA:
                if inputs.get("prefix_http_header_key", ""):
                    content_prefix = request.headers[
                        inputs["prefix_http_header_key"]
                    ]
                else:
                    content_prefix = ""

                obj = EcdsaAuthentication(
                    public_key=inputs["public_key"],
                    signature=request.headers[inputs["http_header_key"]],
                    content_prefix=content_prefix,
                    signature_encoding=inputs["signature_encoding"],
                    hash_algorithm=inputs["hash_algorithm"],
                )
                obj.authenticate(request.body)
            else:
                message = "Unknown auth type"
                logger.error(message)
                raise ParseError(message)
        except AuthenticationFailed as err:
            self._update_stats()
            if self.webhook.test_mode:
                self._update_test_data(
                    error_message=err,
                    headers=yaml.dump(dict(request.headers)),
                )
            raise

    @extend_schema(exclude=True)
    @action(detail=True, methods=["POST"], rbac_action=None)
    def post(self, request, *_args, **kwargs):
        """Handle posts from external webhook vendors."""
        try:
            self.webhook = Webhook.objects.get(uuid=kwargs["pk"])
        except Webhook.DoesNotExist as exc:
            raise ParseError("bad uuid specified") from exc

        logger.debug("Headers %s", request.headers)
        logger.debug("Body %s", request.body)
        inputs = yaml.safe_load(
            self.webhook.eda_credential.inputs.get_secret_value()
        )
        if inputs["http_header_key"] not in request.headers:
            message = f"{inputs['http_header_key']} header is missing"
            logger.error(message)
            if self.webhook.test_mode:
                self._update_test_data(
                    error_message=message,
                    headers=yaml.dump(dict(request.headers)),
                )
            raise ParseError(message)

        self._handle_auth(request, inputs)

        body = self._parse_body(
            request.headers.get("Content-Type", ""), request.body
        )

        # Some sites send in an array or a string
        if isinstance(body, dict):
            data = body
        else:
            data = {"body": body}

        logger.debug("Data: %s", data)

        payload = self._create_payload(
            request.headers,
            data,
            inputs["http_header_key"],
            request.get_full_path(),
        )
        self._update_stats()
        if self.webhook.test_mode:
            self._update_test_data(
                content=yaml.dump(body),
                content_type=request.headers.get("Content-Type", "unknown"),
                headers=yaml.dump(dict(request.headers)),
            )
        else:
            try:
                PGNotify(
                    settings.PG_NOTIFY_DSN_SERVER,
                    self.webhook.channel_name,
                    payload,
                )()
            except PGNotifyError as e:
                logger.error(e)
                return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=status.HTTP_200_OK)
