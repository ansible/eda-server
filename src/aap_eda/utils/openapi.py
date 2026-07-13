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

_FIELD_TYPE_MAP = {
    models.CharField: OpenApiTypes.STR,
    models.IntegerField: OpenApiTypes.NUMBER,
    models.DateField: OpenApiTypes.DATETIME,
    models.BooleanField: OpenApiTypes.BOOL,
}


def _get_openapi_type(field):
    for field_cls, api_type in _FIELD_TYPE_MAP.items():
        if isinstance(field, field_cls):
            return api_type
    return OpenApiTypes.STR


def _resolve_param_name(name, field_names):
    if name in field_names:
        return name
    id_name = f"{name}_id"
    if id_name in field_names:
        return id_name
    return None


def generate_query_params(
    serializer: Serializer,
) -> list[OpenApiParameter]:
    """Generate OpenAPI query parameters dynamically."""
    query_params = []
    model = serializer.Meta.model
    field_names = set(serializer.get_fields().keys())
    for field in model._meta.get_fields():
        param_name = _resolve_param_name(field.name, field_names)
        if param_name is None:
            continue
        query_params.append(
            OpenApiParameter(
                name=param_name,
                description=f"Filter by {param_name}",
                required=False,
                type=_get_openapi_type(field),
            )
        )
    return query_params
