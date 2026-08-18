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

import hashlib
import logging

import yaml

from aap_eda.core.exceptions import ParseError
from aap_eda.core import models

LOGGER = logging.getLogger(__name__)
DEFAULT_SOURCE_NAME_PREFIX = "__SOURCE_"


def build_source_list(rulesets_data: str) -> list[dict]:
    """
    Parse rulesets to build sources.

    Args:
        rulesets_data: rulesets of the rulebook

    Returns:
        list of sources defined in the ruleset

    """
    results = []
    if rulesets_data is None:
        return results

    try:
        rulesets = yaml.safe_load(rulesets_data)
    except yaml.MarkedYAMLError as ex:
        LOGGER.error("Invalid rulesets: %s", str(ex))
        raise ParseError("Failed to parse rulebook data") from ex

    rulebook_hash = get_rulebook_hash(rulesets_data)
    current_names = set()
    counter = 1

    for ruleset in rulesets:
        for source in ruleset.get("sources", []):
            default_name = f"{DEFAULT_SOURCE_NAME_PREFIX}{counter}"
            counter += 1

            src_record = {}
            src_record["rulebook_hash"] = rulebook_hash
            src_record["source_info"] = source

            src_name = source.get("name", default_name)
            if src_name in current_names:
                src_record["name"] = default_name
            else:
                src_record["name"] = source.get("name", default_name)

            current_names.add(src_record["name"])

            results.append(src_record)

    return results


def get_rulebook_hash(rulebook: str) -> str:
    """
    Get the SHA256 hash of rulebook content.

    Args:
        rulebook: string format of rulebook content

    Returns: the hexadecimal representation of the hash
    """
    return hashlib.sha256((rulebook or "").encode("utf-8")).hexdigest()


def swap_event_stream_sources(
    data: str, event_stream_sources: dict, mappings: list[dict]
) -> str:
    """Swap out the sources with event stream sources that match the name.

    Preserve the filters if they exist for the source.
    """
    rulesets = yaml.safe_load(data)
    counter = 1
    current_names = set()

    mapping_dict = {
        mapping["source_name"]: mapping["event_stream_name"]
        for mapping in mappings
    }

    for ruleset in rulesets:
        new_sources = []
        for source in ruleset.get("sources", []):
            default_name = f"{DEFAULT_SOURCE_NAME_PREFIX}{counter}"
            counter += 1

            src_name = source.get("name", default_name)
            if src_name in current_names:
                src_name = default_name

            current_names.add(src_name)

            if src_name in mapping_dict:
                event_stream_name = mapping_dict[src_name]

                if event_stream_name in event_stream_sources:
                    updated_source = _updated_event_stream_source(
                        event_stream_name, source, event_stream_sources
                    )
                    new_sources.append(updated_source)
                    LOGGER.info(
                        "Source %s updated with Event Stream Source",
                        event_stream_name,
                    )
                else:
                    msg = f"No event stream found for source {src_name}"
                    LOGGER.warning(msg)
                    new_sources.append(source)
            else:
                LOGGER.info("Source %s left intact", src_name)
                new_sources.append(source)

        ruleset["sources"] = new_sources

    return yaml.dump(rulesets, sort_keys=False)


def _updated_event_stream_source(
    name: str, source: dict, event_stream_sources: dict
) -> dict:
    updated_source = {"name": name}
    source_type = next(iter(event_stream_sources[name]))
    updated_source[source_type] = event_stream_sources[name][source_type]
    if "filters" in source:
        updated_source["filters"] = source["filters"]
    LOGGER.info("Source %s updated with Event Stream Source", name)
    return updated_source


def update_event_stream_sources_from_mappings(
    rulebook_rulesets: str, source_mappings_yaml: str, pg_notify_dsn: str
) -> str:
    """
    Load source mappings (YAML string), resolve EventStream objects in DB,
    build event stream sources dict and substitute them into the rulebook
    rulesets via swap_event_stream_sources.

    Args:
        rulebook_rulesets: YAML/string rulesets content
        source_mappings_yaml: YAML string (user-provided source mappings)
        pg_notify_dsn: DSN template string to use for pg_listener sources

    Returns:
        Updated rulesets YAML string (returned by swap_event_stream_sources)

    Raises:
        ParseError: on invalid mappings, missing event stream, or other failures
    """
    try:
        source_mappings = yaml.safe_load(source_mappings_yaml)
        sources_info = {}
        for source_map in source_mappings:
            event_stream_id = source_map.get("event_stream_id")
            try:
                obj = models.EventStream.objects.get(id=event_stream_id)
            except models.EventStream.DoesNotExist as exc:
                raise ParseError(f"Event stream id {event_stream_id} not found") from exc

            sources_info[obj.name] = {
                "ansible.eda.pg_listener": {
                    "dsn": pg_notify_dsn,
                    "channels": [obj.channel_name],
                },
            }

        return swap_event_stream_sources(rulebook_rulesets, sources_info, source_mappings)
    except yaml.MarkedYAMLError as ex:
        LOGGER.error("Invalid source mappings YAML: %s", str(ex))
        raise ParseError("Failed to parse source mappings") from ex
    except ParseError:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to update event stream sources: %s", str(ex))
        raise ParseError("Failed to update event stream sources") from ex
