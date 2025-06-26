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
"""Module providing external event stream post."""

import datetime
import logging
import urllib.parse

import yaml
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.http.request import HttpHeaders
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, ParseError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from aap_eda.api.event_stream_authentication import (
    BasicAuthentication,
    EcdsaAuthentication,
    HMACAuthentication,
    MTLSAuthentication,
    Oauth2Authentication,
    Oauth2JwtAuthentication,
    TokenAuthentication,
)
from aap_eda.core.enums import Action, EventStreamAuthType, ResourceType
from aap_eda.core.exceptions import PGNotifyError
from aap_eda.core.models import EventStream
from aap_eda.services.pg_notify import PGNotify

logger = logging.getLogger(__name__)


class ExternalEventStreamViewSet(viewsets.GenericViewSet):
    """External Event Stream View Set."""

    rbac_action = None
    rbac_resource_type = ResourceType.EVENT_STREAM
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_rbac_permission(self):
        """RBAC Permissions."""
        return ResourceType.EVENT_STREAM, Action.READ

    def __init__(self, *args, **kwargs):
        self.event_stream = None
        super().__init__()

    def _update_test_data(
        self,
        error_message: str = "",
        content_type: str = "",
        content: str = "",
        headers: str = "",
    ):
        logger.warning(
            "The event stream: %s is currently in test mode",
            self.event_stream.name,
        )
        self.event_stream.test_error_message = error_message
        self.event_stream.test_content_type = content_type
        self.event_stream.test_content = content
        self.event_stream.test_headers = headers
        self.event_stream.save(
            update_fields=[
                "test_content_type",
                "test_content",
                "test_headers",
                "test_error_message",
            ]
        )

    def _parse_body(self, content_type: str, body: bytes) -> dict:
        if content_type == "application/x-www-form-urlencoded":
            try:
                data = urllib.parse.parse_qs(
                    body.decode(), strict_parsing=True
                )
            except ValueError as exc:
                message = f"Invalid content. Type: {content_type}"
                logger.error(message)
                raise ParseError(message) from exc
        else:
            try:
                data = yaml.safe_load(body.decode())
            except yaml.YAMLError as exc:
                message = f"Invalid content. Type: {content_type}"
                logger.error(message)
                raise ParseError(message) from exc
        return data

    def _create_payload(
        self, headers: HttpHeaders, data: dict, header_key: str, endpoint: str
    ) -> dict:
        event_headers = {}
        if self.event_stream.additional_data_headers:
            for key in self.event_stream.additional_data_headers.split(","):
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
                "eda_event_stream_name": self.event_stream.name,
                "headers": event_headers,
            },
        }

    @transaction.atomic
    def _update_stats(self):
        self.event_stream.events_received = F("events_received") + 1
        self.event_stream.last_event_received_at = datetime.datetime.now(
            tz=datetime.timezone.utc
        )
        self.event_stream.save(
            update_fields=[
                "events_received",
                "last_event_received_at",
            ]
        )

    def _handle_auth(self, request, inputs):
        try:
            if inputs["auth_type"] == EventStreamAuthType.HMAC:
                obj = HMACAuthentication(
                    signature_encoding=inputs["signature_encoding"],
                    signature_prefix=inputs.get("signature_prefix", ""),
                    signature=request.headers[inputs["http_header_key"]],
                    hash_algorithm=inputs["hash_algorithm"],
                    secret=inputs["secret"].encode("utf-8"),
                )
                obj.authenticate(request.body)
            elif inputs["auth_type"] == EventStreamAuthType.MTLS:
                obj = MTLSAuthentication(
                    subject=inputs.get("subject", ""),
                    value=request.headers[inputs["http_header_key"]],
                )
                obj.authenticate()
            elif inputs["auth_type"] == EventStreamAuthType.TOKEN:
                obj = TokenAuthentication(
                    token=inputs["token"],
                    value=request.headers[inputs["http_header_key"]],
                )
                obj.authenticate()
            elif inputs["auth_type"] == EventStreamAuthType.BASIC:
                obj = BasicAuthentication(
                    password=inputs["password"],
                    username=inputs["username"],
                    authorization=request.headers[inputs["http_header_key"]],
                )
                obj.authenticate()
            elif inputs["auth_type"] == EventStreamAuthType.OAUTH2JWT:
                obj = Oauth2JwtAuthentication(
                    jwks_url=inputs["jwks_url"],
                    audience=inputs["audience"],
                    access_token=request.headers[inputs["http_header_key"]],
                )
                obj.authenticate()
            elif inputs["auth_type"] == EventStreamAuthType.OAUTH2:
                obj = Oauth2Authentication(
                    introspection_url=inputs["introspection_url"],
                    token=request.headers[inputs["http_header_key"]],
                    client_id=inputs["client_id"],
                    client_secret=inputs["client_secret"],
                )
                obj.authenticate()
            elif inputs["auth_type"] == EventStreamAuthType.ECDSA:
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
            if self.event_stream.test_mode:
                self._update_test_data(
                    error_message=err,
                    headers=yaml.dump(dict(request.headers)),
                )
            raise

    @extend_schema(exclude=True)
    @action(detail=True, methods=["POST"], rbac_action=None)
    def post(self, request, *_args, **kwargs):
        """Handle posts from external vendors."""
        try:
            self.event_stream = EventStream.objects.get(uuid=kwargs["pk"])
        except (EventStream.DoesNotExist, ValidationError) as exc:
            raise ParseError("bad uuid specified") from exc

        logger.debug("Headers %s", request.headers)
        logger.debug("Body %s", request.body)
        inputs = yaml.safe_load(
            self.event_stream.eda_credential.inputs.get_secret_value()
        )
        if inputs["http_header_key"] not in request.headers:
            message = f"{inputs['http_header_key']} header is missing"
            logger.error(message)
            if self.event_stream.test_mode:
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
        if self.event_stream.test_mode:
            self._update_test_data(
                content=yaml.dump(body),
                content_type=request.headers.get("Content-Type", "unknown"),
                headers=yaml.dump(dict(request.headers)),
            )
        else:
            try:
                PGNotify(
                    settings.PG_NOTIFY_DSN_SERVER,
                    self.event_stream.channel_name,
                    payload,
                )()
            except PGNotifyError as e:
                logger.error(e)
                return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=status.HTTP_200_OK)
