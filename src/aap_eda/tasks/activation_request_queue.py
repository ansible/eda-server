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
from aap_eda.core.models.proxies import ProcessParentProxy


def push(
    process_parent: ProcessParentProxy,
    request: ActivationRequest,
) -> None:
    """Push a process parent request to the queue."""
    kwargs = _build_kwargs(process_parent) | {"request": request}
    ActivationRequestQueue.objects.create(**kwargs)


def peek_all(
    process_parent: ProcessParentProxy,
) -> list[ActivationRequestQueue]:
    kwargs = _build_kwargs(process_parent)
    requests = ActivationRequestQueue.objects.filter(**kwargs).all()
    return _arbitrate(requests)


def pop_until(process_parent: ProcessParentProxy, queue_id: int) -> None:
    kwargs = _build_kwargs(process_parent) | {"id__lte": queue_id}
    ActivationRequestQueue.objects.filter(**kwargs).delete()


def list_activations() -> list[ProcessParentProxy]:
    activations = (
        ActivationRequestQueue.objects.filter(activation_id__isnull=False)
        .order_by("activation_id")
        .distinct("activation_id")
    )

    sources = (
        ActivationRequestQueue.objects.filter(source_id__isnull=False)
        .order_by("source_id")
        .distinct("source_id")
    )

    activation_results = [
        ProcessParentProxy(obj.process_parent) for obj in activations
    ]
    source_results = [
        ProcessParentProxy(obj.process_parent) for obj in sources
    ]
    return activation_results + source_results


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


def _build_kwargs(process_parent: ProcessParentProxy) -> dict:
    """Build kwargs based on the type of process parent."""
    if process_parent.is_activation:
        return {"activation_id": process_parent.id}
    return {"source_id": process_parent.id}
