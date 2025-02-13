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

from django.db import models
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from rest_framework.serializers import Serializer


def generate_query_params(serializer: Serializer) -> list[OpenApiParameter]:
    """Generate OpenAPI query parameters dynamically based on the view's serializer fields and model."""  # noqa: E501
    query_params = []
    model = serializer.Meta.model
    fields = serializer.get_fields()
    field_names = fields.keys()
    for field in model._meta.get_fields():
        # check if model field name is defined in the serializer
        if (
            field.name in field_names
            or "_".join([field.name, "id"]) in field_names
        ):
            param_name = (
                field.name
                if field.name in field_names
                else "_".join([field.name, "id"])
            )
            query_params.append(
                OpenApiParameter(
                    name=param_name,
                    description=f"Filter by {param_name}",
                    required=False,
                    type=(
                        OpenApiTypes.STR
                        if isinstance(field, models.CharField)
                        else OpenApiTypes.NUMBER
                        if isinstance(field, models.IntegerField)
                        else OpenApiTypes.DATETIME
                        if isinstance(field, models.DateField)
                        else OpenApiTypes.BOOL
                        if isinstance(field, models.BooleanField)
                        else OpenApiTypes.STR
                    ),
                )
            )

    return query_params
