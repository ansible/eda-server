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
    monitor_rulebook_process,
    restart_rulebook_process,
    start_rulebook_process,
    stop_rulebook_process,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    destroy=extend_schema(
        description="Delete an existing Activation",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="The Activation has been deleted.",
            ),
        },
    ),
)
class ActivationViewSet(
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.Activation.objects.all()
    serializer_class = serializers.ActivationSerializer
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.ActivationFilter

    rbac_resource_type = None
    rbac_action = None

    @extend_schema(
        request=serializers.ActivationCreateSerializer,
        responses={
            status.HTTP_201_CREATED: serializers.ActivationReadSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Invalid data to create activation."
            ),
        },
    )
    def create(self, request):
        context = {"request": request}
        serializer = serializers.ActivationCreateSerializer(
            data=request.data, context=context
        )
        serializer.is_valid(raise_exception=True)

        activation = serializer.create(serializer.validated_data)

        if activation.is_enabled:
            start_rulebook_process(
                process_parent_type=ProcessParentType.ACTIVATION,
                id=activation.id,
            )

        return Response(
            serializers.ActivationReadSerializer(activation).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        responses={status.HTTP_200_OK: serializers.ActivationReadSerializer},
    )
    def retrieve(self, request, pk: int):
        activation = get_object_or_404(models.Activation, pk=pk)
        return Response(serializers.ActivationReadSerializer(activation).data)

    @extend_schema(
        description="List all Activations",
        request=None,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ActivationListSerializer(many=True),
                description="Return a list of Activations.",
            ),
        },
    )
    def list(self, request):
        activations = models.Activation.objects.all()
        activations = self.filter_queryset(activations)

        serializer = serializers.ActivationListSerializer(
            activations, many=True
        )
        result = self.paginate_queryset(serializer.data)

        return self.get_paginated_response(result)

    def perform_destroy(self, activation):
        activation.status = ActivationStatus.DELETING
        activation.save(update_fields=["status"])
        logger.info(f"Now deleting {activation.name} ...")
        delete_rulebook_process(
            process_parent_type=ProcessParentType.ACTIVATION,
            id=activation.id,
        )

    @extend_schema(
        description="List all instances for the Activation",
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
        activation_exists = models.Activation.objects.filter(id=id).exists()
        if not activation_exists:
            raise api_exc.NotFound(
                code=status.HTTP_404_NOT_FOUND,
                detail=f"Activation with ID={id} does not exist.",
            )

        activation_instances = models.RulebookProcess.objects.filter(
            activation_id=id,
            parent_type=ProcessParentType.ACTIVATION,
        )
        filtered_instances = self.filter_queryset(activation_instances)
        result = self.paginate_queryset(filtered_instances)
        serializer = serializers.ActivationInstanceSerializer(
            result, many=True
        )
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        description="Enable the Activation",
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="Activation has been enabled.",
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                None,
                description="Activation not enabled.",
            ),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                None,
                description="Activation not enabled do to current activation "
                "status",
            ),
        },
    )
    @action(methods=["post"], detail=True, rbac_action=Action.ENABLE)
    def enable(self, request, pk):
        activation = get_object_or_404(models.Activation, pk=pk)

        if activation.is_enabled:
            return Response(status=status.HTTP_204_NO_CONTENT)

        if activation.status in [
            ActivationStatus.STARTING,
            ActivationStatus.STOPPING,
            ActivationStatus.DELETING,
            ActivationStatus.RUNNING,
            ActivationStatus.UNRESPONSIVE,
        ]:
            return Response(status=status.HTTP_409_CONFLICT)

        valid, error = is_activation_valid(activation)
        if not valid:
            activation.status = ActivationStatus.ERROR
            activation.status_message = error
            activation.save(update_fields=["status", "status_message"])
            logger.error(f"Failed to enable {activation.name}: {error}")

            return Response(
                {"errors": error}, status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(f"Now enabling {activation.name} ...")

        activation.is_enabled = True
        activation.failure_count = 0
        activation.status = ActivationStatus.PENDING
        activation.save(
            update_fields=[
                "is_enabled",
                "failure_count",
                "status",
                "modified_at",
            ]
        )
        start_rulebook_process(
            process_parent_type=ProcessParentType.ACTIVATION,
            id=pk,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description="Disable the Activation",
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="Activation has been disabled.",
            ),
        },
    )
    @action(methods=["post"], detail=True, rbac_action=Action.DISABLE)
    def disable(self, request, pk):
        activation = get_object_or_404(models.Activation, pk=pk)

        self._check_deleting(activation)

        if activation.is_enabled:
            activation.status = ActivationStatus.STOPPING
            activation.is_enabled = False
            activation.save(
                update_fields=["is_enabled", "status", "modified_at"]
            )
            stop_rulebook_process(
                process_parent_type=ProcessParentType.ACTIVATION,
                id=activation.id,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description="Refresh the Activation",
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="Activation has been refreshed.",
            ),
        },
    )
    @action(methods=["post"], detail=True, rbac_action=Action.DISABLE)
    def refresh(self, request, pk):
        activation = get_object_or_404(models.Activation, pk=pk)

        monitor_rulebook_process(
            process_parent_type=ProcessParentType.ACTIVATION,
            id=activation.id,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description="Restart the Activation",
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="Activation restart was successful.",
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                None,
                description="Activation not enabled.",
            ),
        },
    )
    @action(methods=["post"], detail=True, rbac_action=Action.RESTART)
    def restart(self, request, pk):
        activation = get_object_or_404(models.Activation, pk=pk)

        self._check_deleting(activation)

        if not activation.is_enabled:
            raise api_exc.Forbidden(
                detail="Activation is disabled and cannot be run."
            )

        valid, error = is_activation_valid(activation)
        if not valid:
            activation.status = ActivationStatus.ERROR
            activation.status_message = error
            activation.save(update_fields=["status", "status_message"])
            logger.error(f"Failed to restart {activation.name}: {error}")

            return Response(
                {"errors": error}, status=status.HTTP_400_BAD_REQUEST
            )

        restart_rulebook_process(
            process_parent_type=ProcessParentType.ACTIVATION,
            id=activation.id,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    def _check_deleting(self, activation):
        if activation.status == ActivationStatus.DELETING:
            raise exceptions.APIException(
                detail="Object is being deleted", code=409
            )


@extend_schema_view(
    retrieve=extend_schema(
        description="Get the Activation Instance by its id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ActivationInstanceSerializer
            ),
        },
    ),
    list=extend_schema(
        description="List all the Activation Instances",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ActivationInstanceSerializer
            ),
        },
    ),
    destroy=extend_schema(
        description="Delete an existing Activation Instance",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="The Activation Instance has been deleted.",
            ),
        },
    ),
)
class ActivationInstanceViewSet(
    viewsets.ReadOnlyModelViewSet,
    mixins.DestroyModelMixin,
):
    queryset = models.RulebookProcess.objects.all()
    serializer_class = serializers.ActivationInstanceSerializer
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.ActivationInstanceFilter
    rbac_resource_type = ResourceType.ACTIVATION_INSTANCE
    rbac_action = None

    @extend_schema(
        description="List all logs for the Activation Instance",
        request=None,
        responses={
            status.HTTP_200_OK: serializers.ActivationInstanceLogSerializer(
                many=True
            )
        },
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="A unique integer value identifying this Activation Instance.",  # noqa: E501
            )
        ],
    )
    @action(
        detail=False,
        queryset=models.RulebookProcessLog.objects.order_by("id"),
        filterset_class=filters.ActivationInstanceLogFilter,
        rbac_action=Action.READ,
        url_path="(?P<id>[^/.]+)/logs",
    )
    def logs(self, request, id):
        instance_exists = models.RulebookProcess.objects.filter(pk=id).exists()
        if not instance_exists:
            raise api_exc.NotFound(
                code=status.HTTP_404_NOT_FOUND,
                detail=f"Activation Instance with ID={id} does not exist.",
            )

        activation_instance_logs = models.RulebookProcessLog.objects.filter(
            activation_instance_id=id
        ).order_by("id")
        activation_instance_logs = self.filter_queryset(
            activation_instance_logs
        )
        results = self.paginate_queryset(activation_instance_logs)
        serializer = serializers.ActivationInstanceLogSerializer(
            results, many=True
        )
        return self.get_paginated_response(serializer.data)
