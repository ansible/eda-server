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

from aap_eda.core.enums import ActivationRequest
from aap_eda.core.models import ActivationRequestQueue


def push(activation_id: int, request: ActivationRequest) -> None:
    ActivationRequestQueue.objects.create(
        activation_id=activation_id, request=request
    )


def peek_all(activation_id: int) -> list[ActivationRequestQueue]:
    return ActivationRequestQueue.objects.filter(
        activation_id=activation_id
    ).all()


def pop_until(activation_id: int, queue_id: int) -> None:
    ActivationRequestQueue.objects.filter(
        activation_id=activation_id, id__lte=queue_id
    ).delete()


def list_activations() -> list[int]:
    objs = ActivationRequestQueue.objects.order_by("activation_id").distinct(
        "activation_id"
    )
    return [obj.activation_id for obj in objs]
