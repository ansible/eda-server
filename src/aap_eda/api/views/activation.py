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
from django.conf import settings
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as defaultfilters
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from aap_eda.api import exceptions as api_exc, filters, serializers
from aap_eda.core import models
from aap_eda.core.enums import Action, ActivationStatus, ResourceType
from aap_eda.tasks.ruleset import activate_rulesets


def handle_activation_create_conflict(activation):
    activation_dependent_objects = [
        (models.Project, "project", activation.get("project_id")),
        (models.Rulebook, "rulebook", activation.get("rulebook_id")),
        (models.ExtraVar, "extra_var", activation.get("extra_var_id")),
    ]
    for object_model, object_name, object_id in activation_dependent_objects:
        if object_id is None:
            continue
        object_exists = object_model.objects.filter(pk=object_id).exists()
        if not object_exists:
            raise api_exc.Unprocessable(
                detail=f"{object_name.capitalize()} with ID={object_id}"
                " does not exist.",
            )
    raise api_exc.Unprocessable(detail="Integrity error.")


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
# REVIEW(cutwater): Since this class implements `create` method,
#   the `CreateModelMixin` is redundant.
class ActivationViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
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
            status.HTTP_201_CREATED: serializers.ActivationReadSerializer
        },
    )
    def create(self, request):
        serializer = serializers.ActivationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            response = serializer.create(
                serializer.validated_data, request.user
            )
        except IntegrityError:
            handle_activation_create_conflict(serializer.validated_data)

        response_serializer = serializers.ActivationSerializer(response)
        activation = self._get_activation_dependent_objects(
            response_serializer.data
        )
        activation["status"] = ActivationStatus.STARTING.value

        if response.is_enabled:
            decision_environment_id = activation["decision_environment_id"]

            activate_rulesets.delay(
                activation_id=response.id,
                decision_environment_id=decision_environment_id,
                deployment_type=settings.DEPLOYMENT_TYPE,
                ws_base_url=settings.WEBSOCKET_BASE_URL,
                ssl_verify=settings.WEBSOCKET_SSL_VERIFY,
            )

        return Response(
            serializers.ActivationReadSerializer(activation).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        responses={status.HTTP_200_OK: serializers.ActivationReadSerializer},
    )
    def retrieve(self, request, pk: int):
        response = super().retrieve(request, pk)
        activation = self._get_activation_dependent_objects(response.data)
        activation["status"] = self._status_from_instances(
            activation, activation["instances"]
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
        response = super().list(request)
        activations = {}
        if response and response.data:
            activations = response.data["results"]

        for activation in activations:
            activation_instances = models.ActivationInstance.objects.filter(
                activation_id=activation["id"]
            )
            activation["status"] = self._status_from_instances(
                activation, activation_instances
            )

        return self.get_paginated_response(activations)

    @extend_schema(
        description="List all instances for the Activation",
        request=None,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ActivationInstanceSerializer(many=True),
                description="Return a list of Activation Instances.",
            ),
        },
    )
    @action(
        detail=True,
        rbac_resource_type=ResourceType.ACTIVATION_INSTANCE,
        rbac_action=Action.READ,
    )
    def instances(self, request, pk):
        activation_exists = models.Activation.objects.filter(id=pk).exists()
        if not activation_exists:
            raise api_exc.NotFound(
                code=status.HTTP_404_NOT_FOUND,
                detail=f"Activation with ID={pk} does not exist.",
            )

        activation_instances = models.ActivationInstance.objects.filter(
            activation_id=pk
        )
        activation_instances = self.paginate_queryset(activation_instances)
        serializer = serializers.ActivationInstanceSerializer(
            activation_instances, many=True
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
        },
    )
    @action(methods=["post"], detail=True, rbac_action=Action.ENABLE)
    def enable(self, request, pk):
        activation = get_object_or_404(models.Activation, pk=pk)
        if activation.is_enabled:
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            activation.is_enabled = True
            activation.save(update_fields=["is_enabled"])

            activate_rulesets.delay(
                activation_id=pk,
                decision_environment_id=activation.decision_environment.id,
                deployment_type=settings.DEPLOYMENT_TYPE,
                ws_base_url=settings.WEBSOCKET_BASE_URL,
                ssl_verify=settings.WEBSOCKET_SSL_VERIFY,
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
        current_instance = (
            models.ActivationInstance.objects.filter(pk=pk)
            .filter(status=ActivationStatus.RUNNING)
            .first()
        )
        if current_instance:
            # TODO(doston): add logic to stop current running instance
            raise api_exc.HttpNotImplemented(
                detail="An instance is currently running for this Activation. "
                "Stop function for Activations is not implemented."
            )

        activation = get_object_or_404(models.Activation, pk=pk)
        activation.is_enabled = False
        activation.restart_count += 1
        activation.save(update_fields=["is_enabled", "restart_count"])

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description="Restart the Activation",
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None,
                description="Activation restart was successful.",
            ),
        },
    )
    @action(methods=["post"], detail=True, rbac_action=Action.RESTART)
    def restart(self, request, pk):
        activation = get_object_or_404(models.Activation, pk=pk)
        if not activation.is_enabled:
            raise api_exc.HttpForbidden(
                detail="Activation is disabled and cannot be run."
            )

        instance_running = (
            models.ActivationInstance.objects.filter(activation_id=pk)
            .filter(status=ActivationStatus.RUNNING)
            .exists()
        )
        if instance_running:
            # TODO(doston): add logic to stop current running instance
            raise api_exc.HttpNotImplemented(
                detail="An instance is currently running for this Activation. "
                "Stop function for Activations is not implemented."
            )
        activate_rulesets.delay(
            activation_id=pk,
            decision_environment_id=activation.decision_environment.id,
            deployment_type=settings.DEPLOYMENT_TYPE,
            ws_base_url=settings.WEBSOCKET_BASE_URL,
            ssl_verify=settings.WEBSOCKET_SSL_VERIFY,
        )

        activation.restart_count += 1
        activation.save(update_fields=["restart_count"])

        return Response(status=status.HTTP_204_NO_CONTENT)

    def _status_from_instances(self, activation, activation_instances):
        if activation_instances:
            return activation_instances.latest("started_at").status
        elif activation["is_enabled"]:
            return ActivationStatus.FAILED.value
        else:
            return ActivationStatus.STOPPED.value

    def _get_activation_dependent_objects(self, activation):
        activation["project"] = (
            models.Project.objects.get(pk=activation["project_id"])
            if activation["project_id"]
            else None
        )
        activation["decision_environment"] = (
            models.DecisionEnvironment.objects.get(
                pk=activation["decision_environment_id"]
            )
            if activation["decision_environment_id"]
            else None
        )
        activation["rulebook"] = (
            models.Rulebook.objects.get(pk=activation["rulebook_id"])
            if activation["rulebook_id"]
            else None
        )
        activation["extra_var"] = (
            models.ExtraVar.objects.get(pk=activation["extra_var_id"])
            if activation["extra_var_id"]
            else None
        )
        activation_instances = models.ActivationInstance.objects.filter(
            activation_id=activation["id"]
        )
        activation["instances"] = activation_instances

        return activation


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
    queryset = models.ActivationInstance.objects.all()
    serializer_class = serializers.ActivationInstanceSerializer
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.ActivationInstanceFilter
    rbac_resource_type = "activation_instance"
    rbac_action = None

    @extend_schema(
        description="List all logs for the Activation Instance",
        responses={
            status.HTTP_200_OK: serializers.ActivationInstanceLogSerializer
        },
    )
    @action(detail=True, rbac_action=Action.READ)
    def logs(self, request, pk):
        instance_exists = models.ActivationInstance.objects.filter(
            pk=pk
        ).exists()
        if not instance_exists:
            raise api_exc.NotFound(
                code=status.HTTP_404_NOT_FOUND,
                detail=f"Activation Instance with ID={pk} does not exist.",
            )

        activation_instance_logs = models.ActivationInstanceLog.objects.filter(
            activation_instance_id=pk
        ).order_by("id")

        activation_instance_logs = self.paginate_queryset(
            activation_instance_logs
        )

        serializer = serializers.ActivationInstanceLogSerializer(
            activation_instance_logs, many=True
        )
        return self.get_paginated_response(serializer.data)
