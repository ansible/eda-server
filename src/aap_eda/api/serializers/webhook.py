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

from rest_framework import serializers

from aap_eda.core import models, validators


class WebhookInSerializer(serializers.ModelSerializer):
    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())
    hmac_algorithm = serializers.CharField(
        default="sha256",
        help_text="Hash algorithm to use",
        validators=[validators.valid_hash_algorithm],
    )
    hmac_format = serializers.CharField(
        default="hex",
        help_text="Hash format to use, hex or base64",
        validators=[validators.valid_hash_format],
    )
    auth_type = serializers.CharField(
        default="hmac",
        help_text="Auth type to use hmac or token or basic",
        validators=[validators.valid_webhook_auth_type],
    )
    additional_data_headers = serializers.ListField(
        required=False,
        allow_null=True,
        child=serializers.CharField(),
    )

    class Meta:
        model = models.Webhook
        fields = [
            "name",
            "type",
            "hmac_algorithm",
            "header_key",
            "auth_type",
            "hmac_signature_prefix",
            "hmac_format",
            "owner",
            "secret",
            "username",
            "test_mode",
            "additional_data_headers",
        ]


class WebhookOutSerializer(serializers.ModelSerializer):
    owner = serializers.SerializerMethodField()

    class Meta:
        model = models.Webhook
        read_only_fields = [
            "id",
            "owner",
            "url",
            "type",
            "created_at",
            "modified_at",
            "test_content_type",
            "test_content",
            "test_error_message",
        ]
        fields = [
            "name",
            "test_mode",
            "hmac_algorithm",
            "header_key",
            "hmac_signature_prefix",
            "hmac_format",
            "auth_type",
            "additional_data_headers",
            "username",
            *read_only_fields,
        ]

    def get_owner(self, obj) -> str:
        return f"{obj.owner.username}"
