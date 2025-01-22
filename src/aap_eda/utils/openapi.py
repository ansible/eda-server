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


def generate_query_params(serializer):
    """Generate OpenAPI query parameters dynamically based on the view's serializer fields and model."""  # noqa: E501
    query_params = []
    model = serializer.Meta.model
    fields = serializer.get_fields()
    field_names = fields.keys()
    for field in model._meta.get_fields():
        if not field.is_relation and field.name in field_names:
            query_params.append(
                OpenApiParameter(
                    name=field.name,
                    description=f"Filter by {field.name}",
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
