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

from django_filters import rest_framework as defaultfilters
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from aap_eda.api import exceptions as api_exc, filters, serializers
from aap_eda.core import models
from aap_eda.core.utils import logging_utils
from aap_eda.utils import str_to_bool

from .mixins import (
    CreateModelMixin,
    PartialUpdateOnlyModelMixin,
    ResponseSerializerMixin,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="List all decision environments",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.DecisionEnvironmentSerializer,
                description="Return a list of decision environment.",
            ),
        },
    ),
    create=extend_schema(
        description="Create a new decision environment.",
        request=serializers.DecisionEnvironmentCreateSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.DecisionEnvironmentSerializer,
                description="Return the new decision environment.",
            ),
        },
    ),
    partial_update=extend_schema(
        description="Partially update a decision environment",
        request=serializers.DecisionEnvironmentCreateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.DecisionEnvironmentSerializer,
                description="Update successful. Return an updated decision environment.",  # noqa: E501
            )
        },
    ),
)
class DecisionEnvironmentViewSet(
    ResponseSerializerMixin,
    CreateModelMixin,
    PartialUpdateOnlyModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.DecisionEnvironment.objects.order_by("id")
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.DecisionEnvironmentFilter

    def filter_queryset(self, queryset):
        return super().filter_queryset(
            queryset.model.access_qs(self.request.user, queryset=queryset)
        )

    def get_serializer_class(self):
        if self.action in ["create", "partial_update"]:
            return serializers.DecisionEnvironmentCreateSerializer
        return serializers.DecisionEnvironmentSerializer

    def get_response_serializer_class(self):
        return serializers.DecisionEnvironmentSerializer

    @extend_schema(
        description="Get a decision environment by id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.DecisionEnvironmentReadSerializer,
                description="Return a decision environment by id.",
            ),
        },
    )
    def retrieve(self, request, pk):
        decision_environment = super().retrieve(request, pk)
        decision_environment.data["eda_credential"] = (
            models.EdaCredential.objects.get(
                pk=decision_environment.data["eda_credential_id"]
            )
            if decision_environment.data["eda_credential_id"]
            else None
        )
        decision_environment.data["organization"] = (
            models.Organization.objects.get(
                pk=decision_environment.data["organization_id"]
            )
            if decision_environment.data["organization_id"]
            else None
        )

        log_msg = f"RESOURCE UPDATE - \
ResourceType: DesicisonEnvironment / \
ResourceName: {decision_environment.data['name']}  / \
Organization: {decision_environment.data['organization']} / \
Description: {decision_environment.data['description']} / \
ImageURL: {decision_environment.data['image_url']} / \
Credential: \
{logging_utils.get_credential_name_from_data(decision_environment)} / \
Action: Read"
        logger.info(log_msg)

        return Response(
            serializers.DecisionEnvironmentReadSerializer(
                decision_environment.data
            ).data
        )

    @extend_schema(
        description="Delete a decision environment by id",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None, description="Delete successful."
            ),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                None, description="Decision Environment in use by Activations."
            ),
        },
        parameters=[
            OpenApiParameter(
                name="force",
                description="Force deletion if there are dependent objects",
                required=False,
                type=bool,
            )
        ],
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        force_delete = str_to_bool(
            request.query_params.get("force", "false"),
        )

        activations_exist = models.Activation.objects.filter(
            decision_environment_id=instance.id
        ).exists()

        if activations_exist and not force_delete:
            raise api_exc.Conflict(
                "Decision Environment is being used by Activations "
                "and cannot be deleted. If you want to force delete, "
                "please add /?force=True query param."
            )

        self.perform_destroy(instance)

        credential_name = instance.eda_credential
        if instance.credential == "None":
            credential_name = instance.eda_credential.name
        log_msg = f"RESOURCE UPDATE - \
ResourceType: DecisionEnvironment / ResourceName: {instance.name} / \
Organization: {instance.organization} / \
Credential: {credential_name} / Description: {instance.description} / \
ImageURL: {instance.image_url} / Action: Delete"
        logger.info(log_msg)
        return Response(status=status.HTTP_204_NO_CONTENT)
