#  Copyright 2023 Red Hat, Inc.
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

from django.db import models

from aap_eda.core.enums import ActivationRequest, ProcessParentType


class ActivationRequestQueue(models.Model):
    class Meta:
        db_table = "core_activation_request_queue"
        ordering = ["id"]

    request = models.TextField(null=False, choices=ActivationRequest.choices())
    process_parent_type = models.TextField(
        choices=ProcessParentType.choices(),
        null=False,
        default=ProcessParentType.ACTIVATION,
    )
    process_parent_id = models.BigIntegerField(null=False)

    # TODO: can be removed later
    activation = models.ForeignKey(
        "Activation", on_delete=models.CASCADE, null=True
    )
    request_id = models.TextField(blank=True)


__all__ = [
    "ActivationRequestQueue",
]
