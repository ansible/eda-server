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

from aap_eda.core.enums import ActivationRequest


class ActivationRequestQueue(models.Model):
    class Meta:
        db_table = "core_activation_request_queue"
        ordering = ["id"]

    request = models.TextField(null=False, choices=ActivationRequest.choices())
    related_type = models.TextField(
        null=True, default="aap_eda.core.models.Activation"
    )
    instance_id = models.BigIntegerField(null=True)
    activation = models.ForeignKey(
        "Activation", on_delete=models.CASCADE, null=True
    )


__all__ = [
    "ActivationRequestQueue",
]
