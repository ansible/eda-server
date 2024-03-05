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

import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models

from aap_eda.core.utils.crypto.fields import EncryptedTextField

__all__ = "Webhook"

EDA_WEBHOOK_CHANNEL_PREFIX = "eda_webhook_"


class Webhook(models.Model):
    class Meta:
        db_table = "core_webhook"
        indexes = [
            models.Index(fields=["id"], name="ix_webhook_id"),
            models.Index(fields=["name"], name="ix_webhook_name"),
            models.Index(fields=["uuid"], name="ix_webhook_uuid"),
        ]

    name = models.TextField(
        null=False, unique=True, help_text="The name of the webhook"
    )
    type = models.TextField(
        null=False, help_text="The type of the webhook", default="generic"
    )
    secret = EncryptedTextField(
        null=False, help_text="The secret for the webhook"
    )
    auth_type = models.TextField(
        null=False,
        default="hmac",
        help_text="The Authentication method to use, hmac or token",
    )
    header_key = models.TextField(
        null=False,
        default="X-Hub-Signature-256",
        help_text=(
            "The HTTP header which will contain the HMAC " "Signature or Token"
        ),
    )
    hmac_algorithm = models.TextField(
        null=False,
        default="sha256",
        help_text="The algorithm to use for HMAC verification",
    )
    hmac_format = models.TextField(
        null=False,
        default="hex",
        help_text="The format of the signature can be base64 or hex",
    )
    hmac_signature_prefix = models.TextField(
        null=False,
        blank=True,
        default="",
        help_text="The prefix in the signature",
    )

    additional_data_headers = ArrayField(
        models.TextField(help_text="The HTTP header"),
        null=True,
        blank=True,
        help_text=(
            "The additional http headers which will "
            "be added to the event data"
        ),
    )

    test_mode = models.BooleanField(
        default=False, help_text="Enable test mode"
    )

    test_content_type = models.TextField(
        null=True,
        default="",
        help_text="The content type of test data, when in test mode",
    )
    test_content = models.TextField(
        null=True,
        default="",
        help_text=(
            "The content recieved, when in test mode, "
            "stored as a yaml string"
        ),
    )
    test_error_message = models.TextField(
        null=True,
        default="",
        help_text="The error message,  when in test mode",
    )

    owner = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        null=False,
        help_text="The user who created the webhook",
    )
    username = models.TextField(
        null=True,
        blank=True,
        default="",
        help_text="The username for basic auth",
    )
    uuid = models.UUIDField(default=uuid.uuid4)
    url = models.TextField(
        null=False,
        help_text="The URL which will be used to post the data to the webhook",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)

    def _get_channel_name(self) -> str:
        """Generate the channel name based on the UUID and prefix."""
        return (
            f"{EDA_WEBHOOK_CHANNEL_PREFIX}"
            f"{str(self.uuid).replace('-','_')}"
        )

    channel_name = property(_get_channel_name)
