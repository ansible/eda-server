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

import redis
from ansible_base.rbac.api.related import check_related_permissions
from ansible_base.rbac.models import RoleDefinition
from django.conf import settings
from django.db import transaction
from django.forms import model_to_dict
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
from aap_eda.core.enums import Action, ActivationStatus, ProcessParentType
from aap_eda.core.utils import logging_utils
from aap_eda.tasks.orchestrator import (
    delete_rulebook_process,
    restart_rulebook_process,
    start_rulebook_process,
    stop_rulebook_process,
)
from aap_eda.utils import str_to_bool

from .mixins import RedisDependencyMixin

logger = logging.getLogger(__name__)

resource_name = "RulebookActivation"


class ActivationViewSet(
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
    RedisDependencyMixin,
):
    queryset = models.Activation.objects.all()
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.ActivationFilter

    rbac_action = None

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return serializers.ActivationUpdateSerializer
        elif (
            self.request.method == "POST"
            and self.request.path == "/api/eda/v1/activations/"
        ):
            return serializers.ActivationCreateSerializer
        else:
            return serializers.ActivationReadSerializer

    def filter_queryset(self, queryset):
        if queryset.model is models.Activation:
            return super().filter_queryset(
                queryset.model.access_qs(self.request.user, queryset=queryset)
            )
        return super().filter_queryset(queryset)

    @extend_schema(
        request=serializers.ActivationCreateSerializer,
        responses={
            status.HTTP_201_CREATED: serializers.ActivationReadSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Invalid data to create activation."
            ),
            status.HTTP_503_SERVICE_UNAVAILABLE: OpenApiResponse(
                description="Dependent service issues"
            ),
        }
        | RedisDependencyMixin.redis_unavailable_response(),
    )
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # If we're expected to run this activation we need redis
        # to be available.
        if serializer.validated_data.get(
            "is_enabled",
            models.activation.DEFAULT_ENABLED,
        ):
            self.redis_is_available()

        with transaction.atomic():
            response = serializer.create(serializer.validated_data)
            check_related_permissions(
                request.user,
                serializer.Meta.model,
                {},
                model_to_dict(response),
            )
            RoleDefinition.objects.give_creator_permissions(
                request.user, response
            )

        if response.is_enabled:
            start_rulebook_process(
                process_parent_type=ProcessParentType.ACTIVATION,
                process_parent_id=response.id,
                request_id=request.headers.get("x-request-id"),
            )

        logger.info(
            logging_utils.generate_simple_audit_log(
                "Create",
                resource_name,
                response.name,
                response.id,
                response.organization,
            )
        )

        return Response(
            serializers.ActivationReadSerializer(response).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=serializers.ActivationUpdateSerializer,
        responses={
            status.HTTP_200_OK: serializers.ActivationReadSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Invalid data to update activation."
            ),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                description="The activation is not allowed to be updated."
            ),
        },
    )
    def partial_update(self, request, pk):
        activation = self.get_object()
        if activation.is_enabled or activation.status in [
            ActivationStatus.STARTING,
            ActivationStatus.STOPPING,
            ActivationStatus.DELETING,
            ActivationStatus.RUNNING,
            ActivationStatus.UNRESPONSIVE,
            ActivationStatus.WORKERS_OFFLINE,
        ]:
            return Response(
                data=(
                    "Activation is not in disabled mode and in stopped status"
                ),
                status=status.HTTP_409_CONFLICT,
            )
        serializer = self.get_serializer(
            instance=activation, data=request.data, partial=True
        )
        serializer.refill_needed_data(request.data, activation)
        serializer.is_valid(raise_exception=True)
        serializer.prepare_update(activation)

        old_data = model_to_dict(activation)
        is_enabled = serializer.validated_data.pop("is_enabled", False)
        with transaction.atomic():
            serializer.update(activation, serializer.validated_data)
            check_related_permissions(
                request.user,
                serializer.Meta.model,
                old_data,
                model_to_dict(activation),
            )

        logger.info(
            logging_utils.generate_simple_audit_log(
                "Update",
                resource_name,
                activation.name,
                activation.id,
                activation.organization,
            )
        )

        if is_enabled:
            response = self._start(request, activation)
            if response.status_code >= status.HTTP_400_BAD_REQUEST:
                return response

        return Response(serializers.ActivationReadSerializer(activation).data)

    @extend_schema(
        description="Delete an existing Activation",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="The Activation has been deleted.",
            ),
        }
        | RedisDependencyMixin.redis_unavailable_response(),
    )
    def destroy(self, request, *args, **kwargs):
        activation = self.get_object()

        if activation.status == ActivationStatus.WORKERS_OFFLINE:
            raise api_exc.Conflict(
                f"An Activation in state '{activation.status}' cannot be "
                "deleted.",
            )

        audit_log = logging_utils.generate_simple_audit_log(
            "Delete",
            resource_name,
            activation.name,
            activation.id,
            activation.organization,
        )

        try:
            with transaction.atomic():
                activation.status = ActivationStatus.DELETING
                activation.save(update_fields=["status"])
                name = activation.name

                delete_rulebook_process(
                    process_parent_type=ProcessParentType.ACTIVATION,
                    process_parent_id=activation.id,
                    request_id=request.headers.get("x-request-id"),
                )
                logger.info(f"Now deleting {name} ...")
        except redis.ConnectionError:
            # If Redis isn't available we'll generate a Conflict (409).
            # Anything else we re-raise the exception.
            self.redis_is_available()
            raise

        logger.info(audit_log)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        responses={status.HTTP_200_OK: serializers.ActivationReadSerializer},
    )
    def retrieve(self, request, pk: int):
        activation = self.get_object()

        logger.info(
            logging_utils.generate_simple_audit_log(
                "Read",
                resource_name,
                activation.name,
                activation.id,
                activation.organization,
            )
        )

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
        activations = self.filter_queryset(self.get_queryset())

        serializer = serializers.ActivationListSerializer(
            activations, many=True
        )
        result = self.paginate_queryset(serializer.data)

        logger.info(
            logging_utils.generate_simple_audit_log(
                "ListActivations",
                resource_name,
                "*",
                "*",
                "*",
            )
        )
        return self.get_paginated_response(result)

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
        rbac_action=Action.READ,
        url_path="(?P<id>[^/.]+)/instances",
    )
    def instances(self, request, id):
        activation_exists = (
            models.Activation.access_qs(request.user).filter(id=id).exists()
        )
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
                description="Processing of enable is disallowed."
            ),
        },
    )
    @action(methods=["post"], detail=True, rbac_action=Action.ENABLE)
    def enable(self, request, pk):
        activation = self.get_object()
        return self._start(request, activation)

    def _start(self, request, activation: models.Activation) -> Response:
        if activation.is_enabled:
            return Response(status=status.HTTP_204_NO_CONTENT)

        if activation.status in [
            ActivationStatus.STARTING,
            ActivationStatus.STOPPING,
            ActivationStatus.DELETING,
            ActivationStatus.RUNNING,
            ActivationStatus.UNRESPONSIVE,
        ]:
            return Response(
                data="Activation not enabled due to current activation status",
                status=status.HTTP_409_CONFLICT,
            )

        valid, error = is_activation_valid(activation)
        if not valid:
            activation.status = ActivationStatus.ERROR
            activation.status_message = error
            activation.save(update_fields=["status", "status_message"])
            logger.error(f"Failed to enable {activation.name}: {error}")

            return Response(
                {"errors": error}, status=status.HTTP_400_BAD_REQUEST
            )

        # Redis must be available in order to perform the enable.
        self.redis_is_available()

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
            process_parent_id=activation.id,
            request_id=request.headers.get("x-request-id"),
        )

        logger.info(
            logging_utils.generate_simple_audit_log(
                "Enable",
                resource_name,
                activation.name,
                activation.id,
                activation.organization,
            )
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
        }
        | RedisDependencyMixin.redis_unavailable_response(),
    )
    @action(methods=["post"], detail=True, rbac_action=Action.DISABLE)
    def disable(self, request, pk):
        activation = self.get_object()

        self._check_deleting(activation)

        if activation.is_enabled:
            # Redis must be available in order to perform the delete.
            self.redis_is_available()

            if activation.status in [
                ActivationStatus.STARTING,
                ActivationStatus.RUNNING,
            ]:
                activation.status = ActivationStatus.STOPPING

            activation.is_enabled = False
            activation.save(
                update_fields=["is_enabled", "status", "modified_at"]
            )
            stop_rulebook_process(
                process_parent_type=ProcessParentType.ACTIVATION,
                process_parent_id=activation.id,
                request_id=request.headers.get("x-request-id"),
            )

        logger.info(
            logging_utils.generate_simple_audit_log(
                "Disable",
                resource_name,
                activation.name,
                activation.id,
                activation.organization,
            )
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
            status.HTTP_409_CONFLICT: OpenApiResponse(
                None,
                description="Activation blocked while Workers offline.",
            ),
        }
        | RedisDependencyMixin.redis_unavailable_response(),
        parameters=[
            OpenApiParameter(
                name="force",
                description="Force restart after worker node offline",
                required=False,
                type=bool,
            )
        ],
    )
    @action(methods=["post"], detail=True, rbac_action=Action.RESTART)
    def restart(self, request, pk):
        activation = self.get_object()
        self._check_deleting(activation)
        force_restart = str_to_bool(
            request.query_params.get("force", "false"),
        )

        if (
            settings.DEPLOYMENT_TYPE == "podman"
            and activation.status == ActivationStatus.WORKERS_OFFLINE
            and not force_restart
        ):
            # block the restart and return an error
            raise api_exc.Conflict(
                "An activation with an activation_status of 'Workers offline' "
                "cannot be Restarted because this will leave an orphaned "
                "container running on one of the 'activation-worker-node's. "
                "If you want to force a restart, please add the "
                "/?force=true query param."
            )
        if not activation.is_enabled:
            raise api_exc.Forbidden(
                detail="Activation is disabled and cannot be run."
            )

        # Redis must be available in order to perform the restart.
        self.redis_is_available()

        valid, error = is_activation_valid(activation)
        if not valid:
            stop_rulebook_process(
                process_parent_type=ProcessParentType.ACTIVATION,
                process_parent_id=activation.id,
                request_id=request.headers.get("x-request-id"),
            )
            activation.status = ActivationStatus.ERROR
            activation.status_message = error
            activation.save(update_fields=["status", "status_message"])
            logger.error(f"Failed to restart {activation.name}: {error}")

            return Response(
                {"errors": error}, status=status.HTTP_400_BAD_REQUEST
            )

        restart_rulebook_process(
            process_parent_type=ProcessParentType.ACTIVATION,
            process_parent_id=activation.id,
            request_id=request.headers.get("x-request-id"),
        )

        logger.info(
            logging_utils.generate_simple_audit_log(
                "Restart",
                resource_name,
                activation.name,
                activation.id,
                activation.organization,
            )
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description="Copy an activation.",
        request=serializers.ActivationCopySerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.ActivationReadSerializer,
                description="Return the copied activation.",
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                None, description="Activation not found."
            ),
        },
    )
    @action(methods=["post"], detail=True, rbac_action=Action.READ)
    def copy(self, request, pk):
        activation = self.get_object()
        serializer = serializers.ActivationCopySerializer(
            instance=activation, data=request.data
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            response = serializer.copy()
            check_related_permissions(
                request.user,
                serializer.Meta.model,
                {},
                model_to_dict(activation),
            )
            RoleDefinition.objects.give_creator_permissions(
                request.user, response
            )

        logger.info(
            logging_utils.generate_simple_audit_log(
                "Copy",
                resource_name,
                response.name,
                response.id,
                response.organization,
            )
        )

        return Response(
            serializers.ActivationReadSerializer(response).data,
            status=status.HTTP_201_CREATED,
        )

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
)
class ActivationInstanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.RulebookProcess.objects.select_related(
        "rulebookprocessqueue",
    )
    serializer_class = serializers.ActivationInstanceSerializer
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.ActivationInstanceFilter
    rbac_action = None

    def filter_queryset(self, queryset):
        if queryset.model is models.RulebookProcess:
            return super().filter_queryset(
                queryset.model.access_qs(self.request.user, queryset=queryset)
            )
        return super().filter_queryset(queryset)

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
        instance_exists = (
            models.RulebookProcess.access_qs(request.user)
            .filter(pk=id)
            .exists()
        )
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
