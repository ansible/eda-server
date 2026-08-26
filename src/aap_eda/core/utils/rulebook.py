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
_PARSE_ERROR_MSG = "Failed to parse rulebook data"

PG_NOTIFY_DSN = (
    "host={{postgres_db_host}} port={{postgres_db_port}} "
    "dbname={{postgres_db_name}} user={{postgres_db_user}} "
    "password={{postgres_db_password}} sslmode={{postgres_sslmode}} "
    "sslcert={{eda.filename.postgres_sslcert|default(None)}} "
    "sslkey={{eda.filename.postgres_sslkey|default(None)}} "
    "sslpassword={{postgres_sslpassword|default(None)}} "
    "sslrootcert={{eda.filename.postgres_sslrootcert|default(None)}}"
)


def _parse_rulesets(rulesets_data: str) -> list:
    """Parse and validate the top-level rulesets YAML structure."""
    try:
        rulesets = yaml.safe_load(rulesets_data)
    except yaml.MarkedYAMLError as ex:
        LOGGER.error("Invalid rulesets: %s", str(ex))
        raise ParseError(_PARSE_ERROR_MSG) from ex

    if not isinstance(rulesets, list):
        raise ParseError(_PARSE_ERROR_MSG)
    return rulesets


def _validated_sources(ruleset: object) -> list:
    """Return the sources list from a ruleset after validation."""
    if not isinstance(ruleset, dict):
        raise ParseError(_PARSE_ERROR_MSG)
    sources = ruleset.get("sources") or []
    if not isinstance(sources, list):
        raise ParseError(_PARSE_ERROR_MSG)
    return sources


def _validate_source(source: object) -> None:
    """Raise ParseError if a source entry is structurally invalid."""
    if not isinstance(source, dict):
        raise ParseError(_PARSE_ERROR_MSG)
    if _get_source_type(source) is None:
        raise ParseError(_PARSE_ERROR_MSG)
    if "name" in source and not isinstance(source["name"], str):
        raise ParseError(_PARSE_ERROR_MSG)


def build_source_list(rulesets_data: str) -> list[dict]:
    """Parse rulesets to build sources.

    Args:
        rulesets_data: rulesets of the rulebook

    Returns:
        list of sources defined in the ruleset
    """
    if rulesets_data is None:
        return []

    rulesets = _parse_rulesets(rulesets_data)
    rulebook_hash = get_rulebook_hash(rulesets_data)
    current_names: set[str] = set()
    counter = 1
    results: list[dict] = []

    for ruleset in rulesets:
        for source in _validated_sources(ruleset):
            _validate_source(source)
            default_name = f"{DEFAULT_SOURCE_NAME_PREFIX}{counter}"
            counter += 1

            src_record: dict = {
                "rulebook_hash": rulebook_hash,
                "source_info": source,
            }

            src_name = source.get("name", default_name)
            if src_name in current_names:
                src_record["name"] = default_name
            else:
                src_record["name"] = source.get("name", default_name)

            current_names.add(src_record["name"])
            results.append(src_record)

    return results


def _get_source_type(source: dict) -> str | None:
    """Extract the plugin type key from a source dict.

    The source dict uses the plugin type as a top-level key
    (e.g. ``ansible.eda.webhook``).  ``name`` and ``filters``
    are reserved sibling keys, so the type is the first key
    that is neither of those.
    """
    for key in source:
        if key not in ("name", "filters"):
            return key
    return None


def rulebook_sources_unchanged(old_rulesets: str, new_rulesets: str) -> bool:
    """Return True when rulebook sources are structurally identical.

    Compares only the attributes that define source identity:
      1. Positional index (source count and order)
      2. Plugin type key (e.g. ``ansible.eda.webhook``)

    Source args, filters, and explicit names are intentionally
    ignored.  Args and filters are swapped/preserved independently
    by ``swap_event_stream_sources()``.  Name changes are handled
    separately via ``build_source_name_updates()``.
    """
    try:
        old_sources = build_source_list(old_rulesets)
        new_sources = build_source_list(new_rulesets)
    except ParseError:
        LOGGER.warning("Failed to parse rulebook sources for comparison")
        return False

    if len(old_sources) != len(new_sources):
        return False

    for old, new in zip(old_sources, new_sources):
        old_type = _get_source_type(old["source_info"])
        new_type = _get_source_type(new["source_info"])
        if old_type != new_type:
            return False

    return True


def build_source_name_updates(
    old_rulesets: str, new_rulesets: str
) -> dict[str, str]:
    """Return a mapping of old source name to new source name.

    Only includes entries where the resolved name actually changed.
    Positional pairing uses the same ordering as ``build_source_list()``.
    Callers should invoke ``rulebook_sources_unchanged()`` first to
    confirm the source structure is compatible.
    """
    try:
        old_sources = build_source_list(old_rulesets)
        new_sources = build_source_list(new_rulesets)
    except ParseError:
        return {}

    updates: dict[str, str] = {}
    for old, new in zip(old_sources, new_sources):
        if old["name"] != new["name"]:
            updates[old["name"]] = new["name"]
    return updates


def get_rulebook_hash(rulebook: str) -> str:
    """
    Get the SHA256 hash of rulebook content.

    Args:
        rulebook: string format of rulebook content

    Returns: the hexadecimal representation of the hash
    """
    return hashlib.sha256((rulebook or "").encode("utf-8")).hexdigest()


def build_rulebook_with_event_streams(validated_data: dict) -> str:
    """Build swapped rulesets from source_mappings and rulebook content.

    Queries EventStream objects referenced in ``source_mappings``,
    builds the ``pg_listener`` source configuration for each, and
    calls ``swap_event_stream_sources`` to produce the final rulesets.

    Args:
        validated_data: dict with ``source_mappings`` (YAML string)
            and ``rulebook_rulesets`` (YAML string) keys.

    Returns:
        YAML string with event-stream sources swapped in.
    """
    from aap_eda.core import models

    source_mappings = yaml.safe_load(validated_data["source_mappings"])
    sources_info = {}
    for source_map in source_mappings:
        event_stream_id = source_map.get("event_stream_id")
        obj = models.EventStream.objects.get(id=event_stream_id)

        sources_info[obj.name] = {
            "ansible.eda.pg_listener": {
                "dsn": PG_NOTIFY_DSN,
                "channels": [obj.channel_name],
            },
        }

    return swap_event_stream_sources(
        validated_data["rulebook_rulesets"], sources_info, source_mappings
    )


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
