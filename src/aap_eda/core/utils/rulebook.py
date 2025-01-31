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
    Get the hash code of rulebook.

    Args:
        rulebook: string format of rulebook

    Returns: the hexadecimal representation of the hash


    """
    if isinstance(rulebook, str):
        rulebook = rulebook.encode("utf-8")

    sha256 = hashlib.sha256()
    sha256.update(rulebook)

    return sha256.hexdigest()


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
                    LOGGER.debug(
                        "Source %s updated with Event Stream Source",
                        event_stream_name,
                    )
                else:
                    msg = f"No event stream found for source {src_name}"
                    LOGGER.warning(msg)
                    new_sources.append(source)
            else:
                LOGGER.debug("Source %s left intact", src_name)
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
    LOGGER.debug("Source %s updated with Event Stream Source", name)
    return updated_source
