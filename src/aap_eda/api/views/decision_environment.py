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

from ansible_base.rbac.api.related import check_related_permissions
from ansible_base.rbac.models import RoleDefinition
from django.db import transaction
from django.forms import model_to_dict
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

from .mixins import ResponseSerializerMixin

logger = logging.getLogger(__name__)


class CreateDecisionEnvironmentMixin(mixins.CreateModelMixin):
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            self.perform_create(serializer)
            check_related_permissions(
                request.user,
                serializer.Meta.model,
                {},
                model_to_dict(serializer.instance),
            )
            RoleDefinition.objects.give_creator_permissions(
                request.user, serializer.instance
            )
        headers = self.get_success_headers(serializer.data)

        response_serializer_class = self.get_response_serializer_class()
        response_serializer = response_serializer_class(serializer.instance)

        log_msg = (
            "Action: Read / "
            "ResourceType: DecisionEnvironment / "
            f"ResourceName: {response_serializer.data['name']} / "
            f"Organization: {logging_utils.get_organization_name_from_data(response_serializer)} / "  # noqa: E501
            f"Description: {response_serializer.data['description']} / "
            f"ImageURL: {response_serializer.data['image_url']} / "
            f"Credential: {logging_utils.get_credential_name_from_data(response_serializer)}"  # noqa: E501
        )
        logger.info(log_msg)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class PartialUpdateOnlyDecisionEnvironmentMixin(mixins.UpdateModelMixin):
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_data = model_to_dict(instance)
        serializer = self.get_serializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            self.perform_update(serializer)
            check_related_permissions(
                request.user,
                serializer.Meta.model,
                old_data,
                model_to_dict(serializer.instance),
            )

        if getattr(instance, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        response_serializer_class = self.get_response_serializer_class()
        response_serializer = response_serializer_class(serializer.instance)

        log_msg = (
            "Action: Update / "
            "ResourceType: DecisionEnvironment / "
            f"ResourceName: {response_serializer.data['name']} / "
            f"Organization: {logging_utils.get_organization_name_from_data(response_serializer)} / "  # noqa: E501
            f"Description: {response_serializer.data['description']} / "
            f"ImageURL: {response_serializer.data['image_url']} / "
            f"Credential: {logging_utils.get_credential_name_from_data(response_serializer)}"  # noqa: E501
        )
        logger.info(log_msg)

        return Response(response_serializer.data)


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
    CreateDecisionEnvironmentMixin,
    PartialUpdateOnlyDecisionEnvironmentMixin,
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

        log_msg = (
            "Action: Read / "
            "ResourceType: DesicisonEnvironment / "
            f"ResourceName: {decision_environment.data['name']}  / "
            f"Organization: {decision_environment.data['organization']} / "
            f"Description: {decision_environment.data['description']} / "
            f"ImageURL: {decision_environment.data['image_url']} / "
            f"Credential: {logging_utils.get_credential_name_from_data(decision_environment)}"  # noqa: E501
        )
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
        log_msg = (
            "Action: Delete / "
            "ResourceType: DecisionEnvironment / "
            f"ResourceName: {instance.name} / "
            f"Organization: {instance.organization} / "
            f"Credential: {credential_name} / "
            f"Description: {instance.description} / "
            f"ImageURL: {instance.image_url}"
        )
        logger.info(log_msg)
        return Response(status=status.HTTP_204_NO_CONTENT)
