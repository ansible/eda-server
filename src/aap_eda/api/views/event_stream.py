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
"""EventStream configuration API Set."""
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
from rest_framework.response import Response

from aap_eda.api import exceptions as api_exc, filters, serializers
from aap_eda.core import models
from aap_eda.core.enums import ResourceType
from aap_eda.core.utils import logging_utils

logger = logging.getLogger(__name__)

resource_name = "EventStream"


class EventStreamViewSet(
    mixins.CreateModelMixin,
    viewsets.ReadOnlyModelViewSet,
    mixins.DestroyModelMixin,
):
    queryset = models.EventStream.objects.order_by("-created_at")
    filter_backends = (defaultfilters.DjangoFilterBackend,)
    filterset_class = filters.EventStreamFilter
    rbac_resource_type = ResourceType.EVENT_STREAM

    def get_serializer_class(self):
        if self.action == "list":
            return serializers.EventStreamOutSerializer
        if self.action == "destroy":
            return serializers.EventStreamOutSerializer
        if self.action == "create":
            return serializers.EventStreamInSerializer
        if self.action == "partial_update":
            return serializers.EventStreamInSerializer

        return serializers.EventStreamOutSerializer

    def get_response_serializer_class(self):
        return serializers.EventStreamOutSerializer

    def filter_queryset(self, queryset):
        return super().filter_queryset(
            queryset.model.access_qs(self.request.user, queryset=queryset)
        )

    @extend_schema(
        description="Get the EventStream by its id",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EventStreamOutSerializer,
                description="Return the event stream by its id.",
            ),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        event_stream = self.get_object()

        logger.info(
            logging_utils.generate_simple_audit_log(
                "Read",
                resource_name,
                event_stream.name,
                event_stream.id,
                event_stream.organization,
            )
        )

        return Response(
            serializers.EventStreamOutSerializer(event_stream).data
        )

    @extend_schema(
        description="Delete a EventStream by its id",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                None, description="Delete successful."
            )
        },
    )
    def destroy(self, request, *args, **kwargs):
        event_stream = self.get_object()
        ref_count = event_stream.activations.count()
        if ref_count > 0:
            raise api_exc.Conflict(
                f"Event stream '{event_stream.name}' is being referenced by "
                f"{ref_count} activation(s) and cannot be deleted"
            )
        self.perform_destroy(event_stream)

        logger.info(
            logging_utils.generate_simple_audit_log(
                "Delete",
                resource_name,
                event_stream.name,
                event_stream.id,
                event_stream.organization,
            )
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description="List all eventstreams",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EventStreamOutSerializer(many=True),
                description="Return a list of eventstreams.",
            ),
        },
    )
    def list(self, request, *args, **kwargs):
        event_streams = models.EventStream.objects.all()
        event_streams = self.filter_queryset(event_streams)
        serializer = serializers.EventStreamOutSerializer(
            event_streams, many=True
        )
        result = self.paginate_queryset(serializer.data)

        logger.info(
            logging_utils.generate_simple_audit_log(
                "List",
                "EventStream",
                "*",
                "*",
                "*",
            )
        )
        return self.get_paginated_response(result)

    @extend_schema(
        request=serializers.EventStreamInSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                serializers.EventStreamOutSerializer,
                description="Return the new event stream.",
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Invalid data to create event stream."
            ),
        },
    )
    def create(self, request, *args, **kwargs):
        context = {"request": request}
        serializer = serializers.EventStreamInSerializer(
            data=request.data,
            context=context,
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            response = serializer.save()
            check_related_permissions(
                request.user,
                serializer.Meta.model,
                {},
                model_to_dict(serializer.instance),
            )
            RoleDefinition.objects.give_creator_permissions(
                request.user, serializer.instance
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
            serializers.EventStreamOutSerializer(response).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=serializers.EventStreamInSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                serializers.EventStreamOutSerializer,
                description="Update successful, return the new event stream.",
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Unable to update event stream."
            ),
        },
    )
    def partial_update(self, request, *args, **kwargs):
        event_stream = self.get_object()
        old_data = model_to_dict(event_stream)
        context = {"request": request}
        serializer = serializers.EventStreamInSerializer(
            event_stream,
            data=request.data,
            context=context,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        if event_stream.test_mode != request.data.get(
            "test_mode", event_stream.test_mode
        ):
            event_stream.test_content_type = ""
            event_stream.test_content = ""
            event_stream.test_headers = ""
            event_stream.test_error_message = ""

        for key, value in serializer.validated_data.items():
            setattr(event_stream, key, value)

        with transaction.atomic():
            event_stream.save()
            check_related_permissions(
                request.user,
                serializer.Meta.model,
                old_data,
                model_to_dict(event_stream),
            )

        logger.info(
            logging_utils.generate_simple_audit_log(
                "Update",
                resource_name,
                event_stream.name,
                event_stream.id,
                event_stream.organization,
            )
        )

        return Response(
            serializers.EventStreamOutSerializer(event_stream).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        description="List all activations for the event stream",
        request=None,
        responses={
            status.HTTP_200_OK: serializers.ActivationListSerializer(
                many=True
            ),
        },
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="A unique integer value identifying this event stream.",  # noqa: E501
            )
        ],
    )
    @action(
        detail=False,
        queryset=models.Activation.objects.order_by("id"),
        filterset_class=filters.ActivationFilter,
        url_path="(?P<id>[^/.]+)/activations",
    )
    def activations(self, request, id):
        if (
            not models.EventStream.access_qs(request.user)
            .filter(id=id)
            .exists()
        ):
            raise api_exc.NotFound(
                code=status.HTTP_404_NOT_FOUND,
                detail=f"Event stream with ID={id} does not exist.",
            )

        event_stream = models.EventStream.objects.get(id=id)
        activations = event_stream.activations.all()

        filtered_activations = self.filter_queryset(activations)
        result = self.paginate_queryset(filtered_activations)
        serializer = serializers.ActivationListSerializer(result, many=True)

        logger.info(
            logging_utils.generate_simple_audit_log(
                "ListActivations",
                resource_name,
                event_stream.name,
                event_stream.id,
                event_stream.organization,
            )
        )
        return self.get_paginated_response(serializer.data)
