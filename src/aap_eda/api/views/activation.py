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

from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.response import Response

from aap_eda.api import serializers
from aap_eda.core import models


@extend_schema_view(
    partial_update=extend_schema(
        request=serializers.ActivationUpdateSerializer,
        description="Partially update the activation by its id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.ActivationSerializer,
                description="The activation has been updated.",
            ),
        },
    ),
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
class ActivationViewSet(viewsets.ModelViewSet):
    queryset = models.Activation.objects.all()
    serializer_class = serializers.ActivationSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    @extend_schema(
        request=serializers.ActivationCreateSerializer,
        responses={status.HTTP_201_CREATED: serializers.ActivationSerializer},
    )
    def create(self, request):
        serializer = serializers.ActivationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        response = models.Activation.objects.create(**data)
        serializer_class = serializers.ActivationSerializer(response)
        # TODO(doston): need to implement backend process and instance creation

        return Response(serializer_class.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        responses={status.HTTP_200_OK: serializers.ActivationReadSerializer},
    )
    def retrieve(self, request, pk):
        activation = super().retrieve(request, pk)
        activation.data["project"] = (
            models.Project.objects.get(pk=activation.data["project"])
            if activation.data["project"]
            else None
        )
        activation.data["rulebook"] = models.Rulebook.objects.get(
            pk=activation.data["rulebook"]
        )
        activation.data["inventory"] = models.Inventory.objects.get(
            pk=activation.data["inventory"]
        )
        activation.data["extra_var"] = (
            models.ExtraVar.objects.get(pk=activation.data["extra_var"])
            if activation.data["extra_var"]
            else None
        )
        activation.data[
            "instances"
        ] = models.ActivationInstance.objects.filter(activation_id=pk)

        return Response(
            serializers.ActivationReadSerializer(activation.data).data
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
    queryset = models.ActivationInstance.objects.all()
    serializer_class = serializers.ActivationInstanceSerializer
