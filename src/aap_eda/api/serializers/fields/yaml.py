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
#
import yaml
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


class YAMLSerializerField(serializers.Field):
    """Serializer for YAML a superset of JSON."""

    def to_internal_value(self, data) -> dict:
        if data:
            try:
                parsed_args = yaml.safe_load(data)
            except yaml.YAMLError:
                raise ValidationError("Invalid YAML format for input data")

            if not isinstance(parsed_args, dict):
                raise ValidationError(
                    "The input field must be a YAML object (dictionary)"
                )

            return parsed_args
        return data

    def to_representation(self, value) -> str:
        return yaml.dump(value)
