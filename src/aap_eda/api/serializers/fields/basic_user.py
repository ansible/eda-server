#  Copyright 2025 Red Hat, Inc.
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
#
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


@extend_schema_field(
    {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "username": {"type": "string"},
            "first_name": {"type": "string"},
            "last_name": {"type": "string"},
        },
    }
)
class BasicUserFieldSerializer(serializers.JSONField):
    """Serializer for Basic User Field."""

    def to_representation(self, value) -> dict:
        return value
