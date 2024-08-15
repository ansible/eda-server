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

from typing import Optional

from ansible_base.rbac.api.related import check_related_permissions
from ansible_base.rbac.models import RoleDefinition
from django.conf import settings
from django.db import transaction
from django.forms import model_to_dict
from drf_spectacular.utils import OpenApiResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.settings import api_settings

from aap_eda.api import exceptions as api_exc
from aap_eda.core import tasking


# TODO: need revisit from cuwater
class CreateModelMixin:
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
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def perform_create(self, serializer):
        serializer.save()

    def get_success_headers(self, data):
        try:
            return {"Location": str(data[api_settings.URL_FIELD_NAME])}
        except (TypeError, KeyError):
            return {}


class PartialUpdateOnlyModelMixin:
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
        return Response(response_serializer.data)

    def perform_update(self, serializer):
        serializer.save()


# TODO: need revisit from cuwater
class ResponseSerializerMixin(object):
    """
    Provide default implementation to get_response_serializer_class.

    The view class should override this method if the response body format
    is different from the request.
    """

    def get_response_serializer_class(self):
        return self.get_serializer_class()


class SharedResourceViewMixin:
    def validate_shared_resource(self):
        if not settings.ALLOW_LOCAL_RESOURCE_MANAGEMENT:
            raise api_exc.Forbidden(
                f"{self.action} should be done through the platform ingress"
            )


class RedisDependencyMixin(object):
    """
    Provides a method which verifies Redis is available.

    Any requested action that depends on Redis (e.g., project creation or
    activation creation with enabled true) to perform the action must validate
    that Redis is accessible by calling the method.

    This is to satisfy the requirement that if the normal and complete
    accomplishment of the action is not achievable due to unavailability of
    Redis that the action is not to be attempted.  This is irresepective of
    whether or not the action would be achieved if/when Redis subsequently
    becomes available.

    The view class may override this method to incorporate checks for specific
    conditions where Redis is/is not required and invoke the superclass method
    for those requiring Redis.
    """

    @staticmethod
    def redis_unavailable_response() -> dict[str, OpenApiResponse]:
        return {
            status.HTTP_409_CONFLICT: OpenApiResponse(
                description="Redis is unavailable.",
            )
        }

    def redis_is_available(
        self,
        message: Optional[str] = "Redis is required but unavailable.",
    ):
        if tasking.is_redis_failed():
            raise api_exc.Conflict(message)
