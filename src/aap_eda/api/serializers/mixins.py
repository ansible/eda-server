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

from django.conf import settings
from rest_framework import serializers

from aap_eda.api import exceptions as api_exc
from aap_eda.core import validators


class SharedResourceSerializerMixin:
    """Serializer mixin which controls the access to shared resources."""

    def validate_shared_resource(self, data=None):
        """
        Validate access to shared resources.

        Here we reject all requests to modify a shared resource if
        ALLOW_LOCAL_RESOURCE_MANAGEMENT is False.

        Call this method from within super().validate().
        """
        if not settings.ALLOW_LOCAL_RESOURCE_MANAGEMENT:
            view = self.context.get("view")
            action = view.action.capitalize() if view else "Action"
            raise api_exc.Forbidden(
                f"{action} should be done through the platform ingress"
            )


class OrganizationIdFieldMixin(serializers.Serializer):
    organization_id = serializers.IntegerField(
        required=True,
        allow_null=False,
        validators=[validators.check_if_organization_exists],
        error_messages={
            "null": "Organization is needed",
            "required": "Organization is required",
        },
    )
