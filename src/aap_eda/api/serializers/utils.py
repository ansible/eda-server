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
from typing import Any, Dict, List, Union

import jinja2
import yaml
from django.conf import settings
from jinja2.nativetypes import NativeTemplate
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

LOGGER = logging.getLogger(__name__)


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


def _render_string(value: str, context: dict) -> str:
    if "{{" in value and "}}" in value:
        return NativeTemplate(value, undefined=jinja2.StrictUndefined).render(
            context
        )

    return value


def _render_string_or_return_value(value: Any, context: Dict) -> Any:
    if isinstance(value, str):
        return _render_string(value, context)
    return value


def substitute_variables(
    value: Union[str, int, Dict, List], context: Dict
) -> Union[str, int, Dict, List]:
    if isinstance(value, str):
        return _render_string_or_return_value(value, context)
    elif isinstance(value, list):
        new_value = []
        for item in value:
            new_value.append(substitute_variables(item, context))
        return new_value
    elif isinstance(value, dict):
        new_value = value.copy()
        for key, subvalue in new_value.items():
            new_value[key] = substitute_variables(subvalue, context)
        return new_value
    else:
        return value


def substitute_source_args(event_stream, source, extra_vars) -> dict:
    context = {
        "settings": settings.__dict__["_wrapped"].__dict__,
        "event_stream": event_stream,
    }
    for key in extra_vars:
        context[key] = extra_vars[key]

    source["args"] = substitute_variables(source.get("args", {}), context)
    return source


def substitute_extra_vars(
    event_stream, extra_vars, encrypt_keys, password
) -> dict:
    context = {
        "settings": settings.__dict__["_wrapped"].__dict__,
        "event_stream": event_stream,
    }
    extra_vars = substitute_variables(extra_vars, context)
    # Encrypt any of the extra_vars
    for key in encrypt_keys:
        if key in extra_vars:
            # extra_vars[key] = encrypt with password
            pass
    return extra_vars


def swap_sources(data: str, sources: list[dict]) -> str:
    rulesets = yaml.safe_load(data)
    new_sources = []
    for source in sources:
        src_obj = {"name": source["name"], source["type"]: source["args"]}
        new_sources.append(src_obj)

    for ruleset in rulesets:
        ruleset["sources"] = new_sources

    return yaml.dump(rulesets)
