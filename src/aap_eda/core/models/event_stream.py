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

from django.db import models

from .base import BaseOrgModel, PrimordialModel, UniqueNamedModel

__all__ = "EventStream"

EDA_EVENT_STREAM_CHANNEL_PREFIX = "eda_event_stream_"


class EventStream(BaseOrgModel, UniqueNamedModel, PrimordialModel):
    event_stream_type = models.TextField(
        null=False,
        help_text="The type of the event stream based on credential type",
        default="hmac",
    )
    eda_credential = models.ForeignKey(
        "EdaCredential",
        blank=True,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
    )
    additional_data_headers = models.TextField(
        blank=True,
        help_text=(
            "The additional http headers which will "
            "be added to the event data. The headers "
            "are comma delimited"
        ),
    )
    test_mode = models.BooleanField(
        default=False, help_text="Enable test mode"
    )
    test_content_type = models.TextField(
        blank=True,
        default="",
        help_text="The content type of test data, when in test mode",
    )
    test_content = models.TextField(
        blank=True,
        default="",
        help_text=(
            "The content recieved, when in test mode, "
            "stored as a yaml string"
        ),
    )
    test_headers = models.TextField(
        blank=True,
        default="",
        help_text=(
            "The headers recieved, when in test mode, "
            "stored as a yaml string"
        ),
    )
    test_error_message = models.TextField(
        blank=True,
        default="",
        help_text="The error message,  when in test mode",
    )
    owner = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        help_text="The user who created the webhook",
    )
    uuid = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)
    events_received = models.BigIntegerField(
        default=0,
        help_text="The total number of events received by event stream",
    )
    last_event_received_at = models.DateTimeField(
        null=True, help_text="The date/time when the last event was received"
    )

    def _get_channel_name(self) -> str:
        """Generate the channel name based on the UUID and prefix."""
        return (
            f"{EDA_EVENT_STREAM_CHANNEL_PREFIX}"
            f"{str(self.uuid).replace('-','_')}"
        )

    channel_name = property(_get_channel_name)
