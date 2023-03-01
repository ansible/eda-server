#  Copyright 2022 Red Hat, Inc.
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

from aap_eda.core.enums import ActivationStatus, RestartPolicy

__all__ = (
    "Activation",
    "ActivationInstance",
    "ActivationInstanceLog",
)


class Activation(models.Model):
    class Meta:
        db_table = "core_activation"
        indexes = [models.Index(fields=["name"], name="ix_activation_name")]

    name = models.TextField(null=False, unique=True)
    description = models.TextField(default="")
    is_enabled = models.BooleanField(default=True)
    execution_environment = models.TextField(
        default="quay.io/aizquier/ansible-rulebook"
    )
    project = models.ForeignKey("Project", on_delete=models.CASCADE, null=True)
    rulebook = models.ForeignKey(
        "Rulebook", on_delete=models.CASCADE, null=False
    )
    extra_var = models.ForeignKey(
        "ExtraVar", on_delete=models.CASCADE, null=True
    )
    restart_policy = models.TextField(
        choices=RestartPolicy.choices(),
        default=RestartPolicy.ON_FAILURE,
    )
    restart_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)


class ActivationInstanceEvent(models.Model):
    """Stores chunked logs."""

    class Meta:
        db_table = "core_activation_instance_event"
        indexes = [
            models.Index(
                fields=["activation_instance", "event_number"],
                name="ix_act_activation_event",
            ),
            models.Index(
                fields=["event_chunk_start_line", "event_chunk_end_line"],
                name="ix_act_event_start_end_line",
            ),
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    activation = models.ForeignKey(
        "Activation", null=False, on_delete=models.CASCADE
    )
    activation_instance = models.ForeignKey(
        "ActivationInstance", on_delete=models.CASCADE
    )
    event_number = models.IntegerField(null=False)
    event_chunk_start_line = models.BigIntegerField(null=False)
    event_chunk_end_line = models.BigIntegerField(null=False)
    event_chunk = models.TextField(null=False, default="")


class ActivationInstance(models.Model):
    class Meta:
        db_table = "core_activation_instance"

    status = models.TextField(
        choices=ActivationStatus.choices(),
        default=ActivationStatus.PENDING,
    )
    activation = models.ForeignKey(
        "Activation", on_delete=models.CASCADE, null=True
    )
    started_at = models.DateTimeField(auto_now_add=True, null=False)
    ended_at = models.DateTimeField(null=True)


class ActivationInstanceLog(models.Model):
    class Meta:
        db_table = "core_activation_instance_log"

    activation_instance = models.ForeignKey(
        "ActivationInstance", on_delete=models.CASCADE
    )
    line_number = models.IntegerField()
    log = models.TextField()
