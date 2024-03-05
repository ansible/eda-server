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
import urllib.parse

import yaml
from django.conf import settings
from django.http.request import HttpHeaders
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, ParseError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from aap_eda.core.enums import Action, ResourceType
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
    ):
        logger.warning(
            f"The webhook: {self.webhook.name} is currently in test mode"
        )
        self.webhook.test_error_message = error_message
        self.webhook.test_content_type = content_type
        self.webhook.test_content = content
        self.webhook.save(
            update_fields=[
                "test_content_type",
                "test_content",
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

    def _embellish_data(self, headers: HttpHeaders, data: dict):
        data["eda_webhook_name"] = self.webhook.name
        if not self.webhook.additional_data_headers:
            return
        for key in self.webhook.additional_data_headers:
            value = headers.get(key)
            if value:
                data[key] = value

    def _hmac_auth(self, body: bytes, signature: str):
        hash_object = hmac.new(
            self.webhook.secret.get_secret_value().encode("utf-8"),
            msg=body,
            digestmod=self.webhook.hmac_algorithm,
        )
        if self.webhook.hmac_format == "hex":
            expected_signature = (
                self.webhook.hmac_signature_prefix + hash_object.hexdigest()
            )
        elif self.webhook.hmac_format == "base64":
            expected_signature = (
                self.webhook.hmac_signature_prefix
                + base64.b64encode(hash_object.digest()).decode()
            )

        if not hmac.compare_digest(expected_signature, signature):
            message = "Signature mismatch, check your payload and secret"
            logger.warning(message)
            if self.webhook.test_mode:
                self._update_test_data(error_message=message)
            raise AuthenticationFailed(message)

    def _token_auth(self, token: str):
        if token.startswith("Bearer"):
            token = token.split("Bearer ")[1]
        if self.webhook.secret.get_secret_value() != token:
            message = "Token mismatch, check your token"
            logger.warning(message)
            if self.webhook.test_mode:
                self._update_test_data(error_message=message)
            raise AuthenticationFailed(message)

    def _basic_auth(self, auth_str: str):
        if auth_str.startswith("Basic"):
            auth_str = auth_str.split("Basic ")[1]
        password = self.webhook.secret.get_secret_value()
        user_pass = f"{self.webhook.username}:{password}"
        b64_value = base64.b64encode(user_pass.encode()).decode()
        if auth_str != b64_value:
            message = "Credential mismatch"
            logger.warning(message)
            if self.webhook.test_mode:
                self._update_test_data(error_message=message)
            raise AuthenticationFailed(message)

    @extend_schema(exclude=True)
    @action(detail=True, methods=["POST"], rbac_action=None)
    def post(self, request, *args, **kwargs):
        try:
            self.webhook = Webhook.objects.get(uuid=kwargs["pk"])
        except Webhook.DoesNotExist:
            raise ParseError("bad uuid specified")

        logger.debug(f"Headers {request.headers}")
        logger.debug(f"Body {request.body}")
        if self.webhook.header_key not in request.headers:
            message = f"{self.webhook.header_key} header is missing"
            logger.error(message)
            if self.webhook.test_mode:
                self._update_test_data(error_message=message)
            raise ParseError(message)

        if self.webhook.auth_type == "hmac":
            self._hmac_auth(
                request.body, request.headers[self.webhook.header_key]
            )
        elif self.webhook.auth_type == "token":
            self._token_auth(request.headers[self.webhook.header_key])
        elif self.webhook.auth_type == "basic":
            self._basic_auth(request.headers[self.webhook.header_key])
        else:
            message = "Unknown auth type"
            logger.error(message)
            raise ParseError(message)

        data = self._parse_body(
            request.headers.get("Content-Type", ""), request.body
        )
        logger.debug(f"Data: {data}")
        self._embellish_data(request.headers, data)
        if self.webhook.test_mode:
            self._update_test_data(
                content=yaml.dump(data),
                content_type=request.headers.get("Content-Type", "unknown"),
            )
        else:
            try:
                PGNotify(
                    settings.PG_NOTIFY_DSN_SERVER,
                    self.webhook.channel_name,
                    data,
                )()
            except Exception as e:
                logger.error(e)
                return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=status.HTTP_200_OK)
