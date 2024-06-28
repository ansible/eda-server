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
    validate_basic_auth,
    validate_ecdsa,
    validate_hmac_auth,
    validate_jwt_access_token,
    validate_mtls_auth,
    validate_oauth_access_token,
    validate_token_auth,
)
from aap_eda.core.enums import Action, ResourceType, WebhookAuthType
from aap_eda.core.models import Webhook
from aap_eda.services.pg_notify import PGNotify

logger = logging.getLogger(__name__)


class ExternalWebhookViewSet(viewsets.GenericViewSet):
    queryset = Webhook.objects.all()
    rbac_action = None
    rbac_resource_type = ResourceType.WEBHOOK
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_rbac_permission(self):
        if self.action == "post":
            return ResourceType.WEBHOOK, Action.READ

    def _update_test_data(
        self,
        error_message: str = "",
        content_type: str = "",
        content: str = "",
        headers: str = "",
    ):
        logger.warning(
            f"The webhook: {self.webhook.name} is currently in test mode"
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
            except Exception:
                message = f"Invalid content type passed {content_type}"
                logger.error(message)
                raise ParseError(message)
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
                validate_hmac_auth(
                    inputs["secret"].encode("utf-8"),
                    inputs["hmac_format"],
                    inputs.get("hmac_signature_prefix", ""),
                    request.body,
                    request.headers[inputs["header_key"]],
                    inputs["hmac_algorithm"],
                )
            elif inputs["auth_type"] == WebhookAuthType.MTLS:
                validate_mtls_auth(
                    inputs.get("certificate_subject", ""),
                    request.headers[inputs["header_key"]],
                )
            elif inputs["auth_type"] == WebhookAuthType.TOKEN:
                validate_token_auth(
                    inputs["secret"],
                    request.headers[inputs["header_key"]],
                )
            elif inputs["auth_type"] == WebhookAuthType.BASIC:
                validate_basic_auth(
                    inputs["username"],
                    inputs["secret"],
                    request.headers[inputs["header_key"]],
                )
            elif inputs["auth_type"] == WebhookAuthType.OAUTH2JWT:
                validate_jwt_access_token(
                    inputs["jwks_url"],
                    inputs["audience"],
                    request.headers[inputs["header_key"]],
                )
            elif inputs["auth_type"] == WebhookAuthType.OAUTH2:
                validate_oauth_access_token(
                    inputs["introspection_url"],
                    request.headers[inputs["header_key"]],
                    inputs["client_id"],
                    inputs["secret"],
                )
            elif inputs["auth_type"] == WebhookAuthType.ECDSA:
                if inputs.get("ecdsa_prefix_header_key", ""):
                    content_prefix = request.headers[
                        inputs["ecdsa_prefix_header_key"]
                    ]
                else:
                    content_prefix = ""

                validate_ecdsa(
                    request.body,
                    inputs["public_key"],
                    request.headers[inputs["header_key"]],
                    content_prefix,
                )
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
    def post(self, request, *args, **kwargs):
        try:
            self.webhook = Webhook.objects.get(uuid=kwargs["pk"])
        except Webhook.DoesNotExist:
            raise ParseError("bad uuid specified")

        logger.debug(f"Headers {request.headers}")
        logger.debug(f"Body {request.body}")
        inputs = yaml.safe_load(
            self.webhook.eda_credential.inputs.get_secret_value()
        )
        if inputs["header_key"] not in request.headers:
            message = f"{inputs['header_key']} header is missing"
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

        logger.debug(f"Data: {data}")

        payload = self._create_payload(
            request.headers,
            data,
            inputs["header_key"],
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
            except Exception as e:
                logger.error(e)
                return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=status.HTTP_200_OK)
