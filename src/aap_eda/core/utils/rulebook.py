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
    except yaml.parser.ParserError as ex:
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
