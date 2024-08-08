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

from aap_eda.api.constants import EDA_SERVER_VAULT_LABEL
from aap_eda.api.vault import encrypt_string

LOGGER = logging.getLogger(__name__)


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

    for key in encrypt_keys:
        if key in extra_vars:
            extra_vars[key] = encrypt_string(
                password=password,
                plaintext=extra_vars[key],
                vault_id=EDA_SERVER_VAULT_LABEL,
            )

    return extra_vars


def swap_sources(data: str, sources: list[dict]) -> str:
    rulesets = yaml.safe_load(data)
    new_sources = []
    for source in sources:
        src_obj = {"name": source["name"], source["type"]: source["args"]}
        new_sources.append(src_obj)

    for ruleset in rulesets:
        ruleset["sources"] = new_sources


def swap_webhook_sources(
    data: str, webhook_sources: dict, swap_single_source: bool
) -> str:
    """Swap out the sources with webhook sources that match the name.

    Preserve the filters if they exist for the source.
    """
    rulesets = yaml.safe_load(data)
    for ruleset in rulesets:
        new_sources = []
        for source in ruleset["sources"]:
            if swap_single_source:
                webhook_name = next(iter(webhook_sources))
                LOGGER.debug("Swapping single source %s", webhook_name)
                updated_source = _updated_webhook_source(
                    webhook_name, source, webhook_sources
                )
                new_sources.append(updated_source)
            elif "name" in source:
                name = source["name"]
                if name in webhook_sources:
                    updated_source = _updated_webhook_source(
                        name, source, webhook_sources
                    )
                    new_sources.append(updated_source)
                    LOGGER.debug("Source %s updated with Webhook Source", name)
                else:
                    LOGGER.debug("Source %s left intact", name)
                    new_sources.append(source)
            else:
                LOGGER.warning(
                    "Source doesn't have a name and cannot be swapped"
                )
                new_sources.append(source)

        ruleset["sources"] = new_sources

    return yaml.dump(rulesets, sort_keys=False)


def _updated_webhook_source(
    name: str, source: dict, webhook_sources: dict
) -> dict:
    updated_source = {"name": name}
    source_type = next(iter(webhook_sources[name]))
    updated_source[source_type] = webhook_sources[name][source_type]
    if "filters" in source:
        updated_source["filters"] = source["filters"]
    LOGGER.debug("Source %s updated with Webhook Source", name)
    return updated_source
