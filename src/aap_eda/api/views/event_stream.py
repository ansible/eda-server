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
import logging

from django.shortcuts import get_object_or_404
from django_filters import rest_framework as defaultfilters
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import exceptions, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from aap_eda.api import exceptions as api_exc, filters, serializers
from aap_eda.api.serializers.activation import is_activation_valid
from aap_eda.core import models
from aap_eda.core.enums import (
    Action,
    ActivationStatus,
    ProcessParentType,
    ResourceType,
)
from aap_eda.tasks.orchestrator import (
    delete_rulebook_process,
    restart_rulebook_process,
    start_rulebook_process,
    stop_rulebook_process,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    destroy=extend_schema(
        description="Delete an existing EventStream",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="The EventStream has been deleted.",
            ),
        },
    ),
)
@extend_schema(exclude=True)
class EventStreamViewSet(
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.EventStream.objects.all().select_related(
        "rulebookprocessqueue",
    )
    serializer_class = serializers.EventStreamSerializer
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.EventStreamFilter
    rbac_resource_type = ResourceType.EVENT_STREAM
    rbac_action = None

    @extend_schema(
        request=serializers.EventStreamCreateSerializer,
        responses={
            status.HTTP_201_CREATED: serializers.EventStreamSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Invalid data to create event_stream."
            ),
        },
    )
    def create(self, request):
        context = {"request": request}
        serializer = serializers.EventStreamCreateSerializer(
            data=request.data, context=context
        )
        serializer.is_valid(raise_exception=True)

        event_stream = serializer.create(serializer.validated_data)

        if event_stream.is_enabled:
            start_rulebook_process(
                process_parent_type=ProcessParentType.EVENT_STREAM,
                process_parent_id=event_stream.id,
            )

        return Response(
            serializers.EventStreamSerializer(event_stream).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        description="Get an event_stream by id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EventStreamSerializer,
                description="Return an event_stream by id.",
            ),
        },
    )
    def retrieve(self, request, pk: int):
        event_stream = get_object_or_404(models.EventStream, pk=pk)
        return Response(serializers.EventStreamSerializer(event_stream).data)

    @extend_schema(
        description="List all EventStreams",
        request=None,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EventStreamSerializer(many=True),
                description="Return a list of EventStreams.",
            ),
        },
    )
    def list(self, request):
        event_streams = models.EventStream.objects.all()
        event_streams = self.filter_queryset(event_streams)

        serializer = serializers.EventStreamSerializer(
            event_streams, many=True
        )
        result = self.paginate_queryset(serializer.data)

        return self.get_paginated_response(result)

    def perform_destroy(self, event_stream):
        event_stream.status = ActivationStatus.DELETING
        event_stream.save(update_fields=["status"])
        logger.info(f"Now deleting {event_stream.name} ...")
        delete_rulebook_process(
            process_parent_type=ProcessParentType.EVENT_STREAM,
            process_parent_id=event_stream.id,
        )

    @extend_schema(
        description="List all instances for the EventStream",
        request=None,
        responses={
            status.HTTP_200_OK: serializers.ActivationInstanceSerializer(
                many=True
            ),
        },
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="A unique integer value identifying this rulebook.",  # noqa: E501
            )
        ],
    )
    @action(
        detail=False,
        queryset=models.RulebookProcess.objects.order_by("id"),
        filterset_class=filters.ActivationInstanceFilter,
        rbac_resource_type=ResourceType.ACTIVATION_INSTANCE,
        rbac_action=Action.READ,
        url_path="(?P<id>[^/.]+)/instances",
    )
    def instances(self, request, id):
        event_stream_exists = models.EventStream.objects.filter(id=id).exists()
        if not event_stream_exists:
            raise api_exc.NotFound(
                code=status.HTTP_404_NOT_FOUND,
                detail=f"EventStream with ID={id} does not exist.",
            )

        event_stream_instances = models.RulebookProcess.objects.filter(
            parent_type=ProcessParentType.EVENT_STREAM,
            event_stream_id=id,
        )
        filtered_instances = self.filter_queryset(event_stream_instances)
        result = self.paginate_queryset(filtered_instances)
        serializer = serializers.ActivationInstanceSerializer(
            result, many=True
        )
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        description="Enable the EventStream",
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="EventStream has been enabled.",
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                None,
                description="EventStream not enabled.",
            ),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                None,
                description="EventStream not enabled do to current event"
                " stream status",
            ),
        },
    )
    @action(methods=["post"], detail=True, rbac_action=Action.ENABLE)
    def enable(self, request, pk):
        event_stream = get_object_or_404(models.EventStream, pk=pk)

        if event_stream.is_enabled:
            return Response(status=status.HTTP_204_NO_CONTENT)

        if event_stream.status in [
            ActivationStatus.STARTING,
            ActivationStatus.STOPPING,
            ActivationStatus.DELETING,
            ActivationStatus.RUNNING,
            ActivationStatus.UNRESPONSIVE,
        ]:
            return Response(status=status.HTTP_409_CONFLICT)

        valid, error = is_activation_valid(event_stream)
        if not valid:
            event_stream.status = ActivationStatus.ERROR
            event_stream.status_message = error
            event_stream.save(update_fields=["status", "status_message"])
            logger.error(f"Failed to enable {event_stream.name}: {error}")

            return Response(
                {"errors": error}, status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(f"Now enabling {event_stream.name} ...")

        event_stream.is_enabled = True
        event_stream.failure_count = 0
        event_stream.status = ActivationStatus.PENDING
        event_stream.save(
            update_fields=[
                "is_enabled",
                "failure_count",
                "status",
                "modified_at",
            ]
        )
        start_rulebook_process(
            process_parent_type=ProcessParentType.EVENT_STREAM,
            process_parent_id=pk,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description="Disable the EventStream",
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="EventStream has been disabled.",
            ),
        },
    )
    @action(methods=["post"], detail=True, rbac_action=Action.DISABLE)
    def disable(self, request, pk):
        event_stream = get_object_or_404(models.EventStream, pk=pk)

        self._check_deleting(event_stream)

        if event_stream.is_enabled:
            event_stream.status = ActivationStatus.STOPPING
            event_stream.is_enabled = False
            event_stream.save(
                update_fields=["is_enabled", "status", "modified_at"]
            )
            stop_rulebook_process(
                process_parent_type=ProcessParentType.EVENT_STREAM,
                process_parent_id=event_stream.id,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description="Restart the EventStream",
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="EventStream restart was successful.",
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                None,
                description="EventStream not enabled.",
            ),
        },
    )
    @action(methods=["post"], detail=True, rbac_action=Action.RESTART)
    def restart(self, request, pk):
        event_stream = get_object_or_404(models.EventStream, pk=pk)

        self._check_deleting(event_stream)

        if not event_stream.is_enabled:
            raise api_exc.Forbidden(
                detail="EventStream is disabled and cannot be run."
            )

        valid, error = is_activation_valid(event_stream)
        if not valid:
            event_stream.status = ActivationStatus.ERROR
            event_stream.status_message = error
            event_stream.save(update_fields=["status", "status_message"])
            logger.error(f"Failed to restart {event_stream.name}: {error}")

            return Response(
                {"errors": error}, status=status.HTTP_400_BAD_REQUEST
            )

        restart_rulebook_process(
            process_parent_type=ProcessParentType.EVENT_STREAM,
            process_parent_id=event_stream.id,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    def _check_deleting(self, event_stream):
        if event_stream.status == ActivationStatus.DELETING:
            raise exceptions.APIException(
                detail="Object is being deleted", code=409
            )
