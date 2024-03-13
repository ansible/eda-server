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


def push(parent_type: str, parent_id: int, request: ActivationRequest) -> None:
    ActivationRequestQueue.objects.create(
        process_parent_type=parent_type,
        process_parent_id=parent_id,
        request=request,
    )


def peek_all(parent_type: str, parent_id: int) -> list[ActivationRequestQueue]:
    requests = ActivationRequestQueue.objects.filter(
        process_parent_type=parent_type, process_parent_id=parent_id
    ).all()
    return _arbitrate(requests)


def pop_until(parent_type: str, parent_id: int, queue_id: int) -> None:
    ActivationRequestQueue.objects.filter(
        process_parent_type=parent_type,
        process_parent_id=parent_id,
        id__lte=queue_id,
    ).delete()


def list_requests() -> list[str, int]:
    objs = ActivationRequestQueue.objects.order_by(
        "process_parent_id"
    ).distinct("process_parent_type", "process_parent_id")
    return [(obj.process_parent_type, obj.process_parent_id) for obj in objs]


def _arbitrate(
    requests: list[ActivationRequestQueue],
) -> list[ActivationRequestQueue]:
    if len(requests) < 2:
        return requests

    ref_request = None
    qualified_requests = []
    starts = [ActivationRequest.START, ActivationRequest.RESTART]
    for request in requests:
        if not ref_request:
            ref_request = request
            continue

        # nothing can be done after delete
        # or dedup
        # or skip auto_start
        if (
            ref_request.request == ActivationRequest.DELETE
            or request.request == ref_request.request
            or request.request == ActivationRequest.AUTO_START
        ):
            request.delete()
            continue

        if ref_request.request == ActivationRequest.AUTO_START:
            ref_request.delete()
            ref_request = request
            continue

        if (
            request.request == ActivationRequest.STOP
            or request.request == ActivationRequest.DELETE
        ):
            while qualified_requests:
                qualified = qualified_requests.pop()
                qualified.delete()
            ref_request.delete()
            ref_request = request
            continue

        if request.request in starts and ref_request.request in starts:
            request.delete()
            continue

        qualified_requests.append(ref_request)
        ref_request = request

    if ref_request:
        qualified_requests.append(ref_request)

    return qualified_requests
