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

from aap_eda.core.enums import RestartPolicy

__all__ = "Source"


class Source(models.Model):
    class Meta:
        db_table = "core_source"
        indexes = [
            models.Index(fields=["id"], name="ix_source_id"),
            models.Index(fields=["name"], name="ix_source_name"),
        ]

    uuid = models.UUIDField(default=uuid.uuid4)
    type = models.TextField(null=False)
    name = models.TextField(null=False, unique=True)
    args = models.JSONField(null=True, default=None)
    listener_args = models.JSONField(null=True, default=None)
    restart_policy = models.TextField(
        choices=RestartPolicy.choices(),
        default=RestartPolicy.ON_FAILURE,
    )
    is_enabled = models.BooleanField(default=True)

    listener_activation = models.ForeignKey(
        "Activation", on_delete=models.SET_NULL, null=True
    )
    decision_environment = models.ForeignKey(
        "DecisionEnvironment", on_delete=models.SET_NULL, null=True
    )
    user = models.ForeignKey("User", on_delete=models.CASCADE, null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)
