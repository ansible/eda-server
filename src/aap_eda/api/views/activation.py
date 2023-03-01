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
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from aap_eda.api import exceptions as api_exc, serializers
from aap_eda.core import models
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
    list=extend_schema(
        description="List all activations",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ActivationSerializer,
                description="A list of all activations is returned.",
            ),
        },
    ),
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
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.Activation.objects.order_by("id")
    serializer_class = serializers.ActivationSerializer

    @extend_schema(
        request=serializers.ActivationCreateSerializer,
        responses={status.HTTP_201_CREATED: serializers.ActivationSerializer},
    )
    def create(self, request):
        serializer = serializers.ActivationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            response = serializer.create(serializer.validated_data)
        except IntegrityError:
            handle_activation_create_conflict(serializer.validated_data)

        response_serializer = serializers.ActivationSerializer(response)
        # TODO(doston): need to implement backend process and instance creation

        return Response(
            response_serializer.data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        responses={status.HTTP_200_OK: serializers.ActivationReadSerializer},
    )
    def retrieve(self, request, pk):
        activation = super().retrieve(request, pk)
        activation.data["project"] = (
            models.Project.objects.get(pk=activation.data["project_id"])
            if activation.data["project_id"]
            else None
        )
        activation.data["rulebook"] = models.Rulebook.objects.get(
            pk=activation.data["rulebook_id"]
        )
        activation.data["extra_var"] = (
            models.ExtraVar.objects.get(pk=activation.data["extra_var_id"])
            if activation.data["extra_var_id"]
            else None
        )
        activation.data[
            "instances"
        ] = models.ActivationInstance.objects.filter(activation_id=pk)

        return Response(
            serializers.ActivationReadSerializer(activation.data).data
        )

    @extend_schema(
        request=serializers.ActivationUpdateSerializer,
        responses={status.HTTP_200_OK: serializers.ActivationSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if getattr(instance, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    @extend_schema(
        description="List all instances for the Activation",
        request=None,
        responses={
            status.HTTP_200_OK: serializers.ActivationInstanceSerializer
        },
    )
    @action(detail=True)
    def instances(self, request, pk):
        activation_exists = models.Activation.objects.filter(pk=pk).exists()
        if not activation_exists:
            raise api_exc.NotFound(
                code=status.HTTP_404_NOT_FOUND,
                detail=f"Activation with id {pk} does not exist.",
            )
        activation_instances = models.ActivationInstance.objects.filter(
            activation_id=pk
        )

        activation_instances = self.paginate_queryset(activation_instances)
        serializer = serializers.ActivationInstanceSerializer(
            activation_instances, many=True
        )
        return self.get_paginated_response(serializer.data)


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
    mixins.CreateModelMixin,
    viewsets.ReadOnlyModelViewSet,
    mixins.DestroyModelMixin,
):
    queryset = models.ActivationInstance.objects.all()
    serializer_class = serializers.ActivationInstanceSerializer

    @extend_schema(
        request=serializers.ActivationInstanceCreateSerializer,
        responses={
            status.HTTP_201_CREATED: serializers.ActivationInstanceSerializer
        },
    )
    def create(self, request):
        serializer = serializers.ActivationInstanceCreateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        response = serializer.create(serializer.validated_data)

        activation = models.Activation.objects.get(id=response.activation_id)
        activate_rulesets.delay(
            response.id,
            activation.execution_environment,
            activation.working_directory,
            settings.DEPLOYMENT_TYPE,
            settings.DOCKER_SERVER_NAME,
            settings.DOCKER_PORT_NUMBER,
        )

        response_serializer = serializers.ActivationInstanceSerializer(
            response
        )

        return Response(
            response_serializer.data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        description="List all logs for the Activation Instance",
        responses={
            status.HTTP_200_OK: serializers.ActivationInstanceLogSerializer
        },
    )
    @action(detail=True)
    def logs(self, request, pk):
        instance_exists = models.Activation.objects.filter(pk=pk).exists()
        if not instance_exists:
            raise api_exc.NotFound(
                code=status.HTTP_404_NOT_FOUND,
                detail=f"Activation Instance with id {pk} does not exist.",
            )

        activation_instance_logs = models.ActivationInstanceLog.objects.filter(
            activation_instance_id=pk
        )

        activation_instance_logs = self.paginate_queryset(
            activation_instance_logs
        )

        serializer = serializers.ActivationInstanceLogSerializer(
            activation_instance_logs, many=True
        )
        return self.get_paginated_response(serializer.data)
