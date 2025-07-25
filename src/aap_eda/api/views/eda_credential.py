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

from ansible_base.rbac.api.related import check_related_permissions
from ansible_base.rbac.models import RoleDefinition
from django.db import transaction
from django.forms import model_to_dict
from django_filters import rest_framework as defaultfilters
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import BaseFilterBackend
from rest_framework.response import Response

from aap_eda.analytics.utils import get_analytics_interval_if_exist
from aap_eda.api import exceptions, exceptions as api_exc, filters, serializers
from aap_eda.api.serializers.eda_credential import get_references
from aap_eda.core import models
from aap_eda.core.enums import Action
from aap_eda.core.utils.credential_plugins import run_plugin
from aap_eda.core.utils.credentials import (
    build_copy_post_data,
    inputs_to_store,
    inputs_to_store_dict,
)
from aap_eda.tasks.analytics import reschedule_gather_analytics
from aap_eda.utils import str_to_bool

from .mixins import (
    CreateModelMixin,
    PartialUpdateOnlyModelMixin,
    ResponseSerializerMixin,
)

logger = logging.getLogger(__name__)


class KindFilterBackend(BaseFilterBackend):
    def filter_queryset(self, request, queryset, _view):
        kinds = request.GET.getlist("credential_type__kind")
        if bool(kinds):
            return queryset.filter(credential_type__kind__in=kinds)

        kinds = request.GET.get("credential_type__kind__in")
        if bool(kinds):
            kinds = kinds.split(",")
            return queryset.filter(credential_type__kind__in=kinds)

        return queryset


class EdaCredentialViewSet(
    ResponseSerializerMixin,
    CreateModelMixin,
    PartialUpdateOnlyModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.EdaCredential.objects.all()
    serializer_class = serializers.EdaCredentialSerializer
    filter_backends = (
        KindFilterBackend,
        defaultfilters.DjangoFilterBackend,
    )
    filterset_class = filters.EdaCredentialFilter
    ordering_fields = ["name"]
    rbac_action = None

    def filter_queryset(self, queryset):
        if queryset.model is models.EdaCredential:
            return super().filter_queryset(
                queryset.model.access_qs(self.request.user, queryset=queryset)
            )
        return super().filter_queryset(queryset)

    @extend_schema(
        description="Get EDA credential by id",
        parameters=[
            OpenApiParameter(
                "refs",
                required=False,
                enum=["true", "false"],
                description=(
                    "Query resources that have reference to the credential"
                    " by its id"
                ),
            ),
        ],
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EdaCredentialSerializer,
                description="Return an EDA credential by id.",
            ),
        },
    )
    def retrieve(self, request, pk):
        eda_credential = self.get_object()
        eda_credential_serializers = serializers.EdaCredentialSerializer(
            eda_credential
        )

        refs = str_to_bool(request.query_params.get("refs", "false"))

        eda_credential_serializers.references = (
            get_references(eda_credential) if refs else None
        )

        return Response(eda_credential_serializers.data)

    @extend_schema(
        description="Create a new EDA credential.",
        request=serializers.EdaCredentialCreateSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.EdaCredentialSerializer,
                description="Return the new EDA credential.",
            ),
        },
    )
    def create(self, request):
        return self._create_eda_credential(request, request.data)

    @extend_schema(
        description="List all EDA credentials",
        parameters=[
            OpenApiParameter(
                "credential_type__kind",
                type=str,
                description="Kind of CredentialType",
            ),
        ],
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EdaCredentialSerializer(many=True),
                description="Return a list of EDA credentials.",
            ),
        },
    )
    def list(self, request):
        credentials = self.get_queryset().exclude(managed=True)
        credentials = self.filter_queryset(credentials)

        serializer = serializers.EdaCredentialSerializer(
            credentials, many=True
        )
        result = self.paginate_queryset(serializer.data)

        return self.get_paginated_response(result)

    @extend_schema(
        description="Partial update of an EDA credential",
        request=serializers.EdaCredentialUpdateSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EdaCredentialSerializer,
                description=(
                    "Update successful. Return an updated EDA credential."
                ),
            )
        },
    )
    def partial_update(self, request, pk):
        eda_credential = self.get_object()
        data = request.data

        data["inputs"] = inputs_to_store_dict(
            data.get("inputs", {}), eda_credential.inputs
        )

        serializer = serializers.EdaCredentialUpdateSerializer(
            eda_credential, data=data, partial=True
        )
        serializer.is_valid(raise_exception=True)

        inputs = serializer.validated_data.get("inputs")
        if inputs or inputs == {}:
            serializer.validated_data["inputs"] = inputs_to_store(
                inputs,
                eda_credential.inputs,
            )

        old_interval = get_analytics_interval_if_exist(eda_credential)
        old_data = model_to_dict(eda_credential)
        for key, value in serializer.validated_data.items():
            setattr(eda_credential, key, value)

        with transaction.atomic():
            eda_credential.save()
            check_related_permissions(
                request.user,
                serializer.Meta.model,
                old_data,
                model_to_dict(eda_credential),
            )

        eda_credential.refresh_from_db()
        new_interval = get_analytics_interval_if_exist(eda_credential)
        if new_interval != old_interval:
            reschedule_gather_analytics()
        return Response(
            serializers.EdaCredentialSerializer(eda_credential).data,
        )

    @extend_schema(
        description="Delete an eda credential by id",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None, description="Delete successful."
            )
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
        force = str_to_bool(request.query_params.get("force", "false"))
        eda_credential = self.get_object()
        if eda_credential.managed:
            error = "Managed EDA credential cannot be deleted"
            return Response(
                {"errors": error}, status=status.HTTP_400_BAD_REQUEST
            )

        if models.EventStream.objects.filter(
            eda_credential=eda_credential
        ).exists():
            raise exceptions.Conflict(
                f"Credential {eda_credential.name} is being referenced by "
                "some event streams and cannot be deleted. "
                "Please delete the EventStream(s) first before the credential "
                "can be deleted. The EventStream maybe in use by other users "
                "in the system."
            )

        references = get_references(eda_credential)

        if bool(references) and not force:
            raise exceptions.Conflict(
                f"Credential {eda_credential.name} is being referenced by "
                "other resources and cannot be deleted. If you want to force "
                "delete, please add /?force=true query param."
            )
        self.perform_destroy(eda_credential)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description="Copy an EDA credential.",
        request=serializers.EdaCredentialCopySerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.EdaCredentialSerializer,
                description="Return the copied EDA credential.",
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                None, description="EDA credential not found."
            ),
        },
    )
    @action(methods=["post"], detail=True, rbac_action=Action.READ)
    def copy(self, request, pk):
        eda_credential = self.get_object()
        post_data = build_copy_post_data(
            eda_credential, request.data.get("name")
        )
        return self._create_eda_credential(request, post_data)

    @extend_schema(
        description="Test an external EDA credential.",
        request=serializers.EdaCredentialTestSerializer,
        responses={
            status.HTTP_202_ACCEPTED: OpenApiResponse(
                None,
                description="Test was successful.",
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                None, description="Test failed."
            ),
        },
    )
    @action(methods=["post"], detail=True, rbac_action=Action.READ)
    def test(self, request, pk):
        eda_credential = self.get_object()
        serializer = serializers.EdaCredentialTestSerializer(
            data=request.data, instance=eda_credential
        )
        serializer.is_valid(raise_exception=True)

        try:
            run_plugin(
                eda_credential.credential_type.namespace,
                serializer.validated_data["inputs"],
                serializer.validated_data["metadata"],
            )
        except Exception as err:
            logger.error(
                "Plugin : %s call failed %s",
                eda_credential.credential_type.namespace,
                err,
            )
            return Response(status=status.HTTP_400_BAD_REQUEST, data={})

        return Response(status=status.HTTP_202_ACCEPTED, data={})

    @extend_schema(
        description="List all input_sources for the Credential",
        request=None,
        responses={
            status.HTTP_200_OK: serializers.CredentialInputSourceSerializer(
                many=True
            ),
        },
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description=(
                    "A unique integer value identifying this credential."
                ),
            )
        ],
    )
    @action(
        detail=False,
        rbac_action=Action.READ,
        url_path="(?P<id>[^/.]+)/input_sources",
    )
    def input_sources(self, request, id):
        credential_exists = (
            models.EdaCredential.access_qs(request.user).filter(id=id).exists()
        )
        if not credential_exists:
            raise api_exc.NotFound(
                code=status.HTTP_404_NOT_FOUND,
                detail=f"Credential with ID={id} does not exist.",
            )

        input_sources = models.CredentialInputSource.objects.filter(
            target_credential_id=id,
        )
        result = self.paginate_queryset(input_sources)
        serializer = serializers.CredentialInputSourceSerializer(
            result, many=True
        )
        return self.get_paginated_response(serializer.data)

    def _create_eda_credential(self, request, data):
        """Create a new credential object given payload data."""
        serializer = serializers.EdaCredentialCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data["inputs"] = inputs_to_store(
            serializer.validated_data["inputs"]
        )
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

        if get_analytics_interval_if_exist(response) > 0:
            reschedule_gather_analytics()

        return Response(
            serializers.EdaCredentialSerializer(response).data,
            status=status.HTTP_201_CREATED,
        )
