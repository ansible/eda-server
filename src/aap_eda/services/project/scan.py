#  Copyright 2023 Red Hat, Inc.
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

import enum
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

import yaml

from .common import StrPath

logger = logging.getLogger(__name__)


IGNORED_DIRS = (".git", ".github")
YAML_EXTENSIONS = (".yml", ".yaml")


class EntryKind(enum.Enum):
    RULEBOOK = "rulebook"
    INVENTORY = "inventory"
    EXTRA_VARS = "extra_vars"
    PLAYBOOK = "playbook"


@dataclass
class ScanResult:
    kind: EntryKind
    filename: str
    raw_content: str
    content: Any


def scan_file(path: Path) -> Optional[ScanResult]:
    if path.suffix not in YAML_EXTENSIONS:
        return None

    try:
        with path.open() as f:
            raw_content = f.read()
    except OSError as exc:
        logger.warning("Cannot open file %s: %s", path.name, exc)
        return None

    try:
        content = yaml.safe_load(raw_content)
    except yaml.YAMLError as exc:
        logger.warning("Invalid YAML file %s: %s", path.name, exc)
        return None

    kind = guess_entry_kind(content)
    return ScanResult(
        kind=kind,
        filename=path.name,
        raw_content=raw_content,
        content=content,
    )


def guess_entry_kind(data: Any) -> EntryKind:
    if is_rulebook_file(data):
        return EntryKind.RULEBOOK
    elif is_inventory_file(data):
        return EntryKind.INVENTORY
    elif is_playbook_file(data):
        return EntryKind.PLAYBOOK
    else:
        return EntryKind.EXTRA_VARS


def is_rulebook_file(data: Any) -> bool:
    if not isinstance(data, list):
        return False
    return all("rules" in entry for entry in data)


def is_playbook_file(data: Any) -> bool:
    if not isinstance(data, list):
        return False
    for entry in data:
        if not isinstance(entry, dict):
            return False
        if entry.keys() & {"tasks", "roles"}:
            return True
    return False


def is_inventory_file(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    return "all" in data


def scan_project(path: StrPath) -> Iterator[ScanResult]:
    for root, dirs, files in os.walk(path):
        # Skip ignored directories
        dirs[:] = [x for x in dirs if x not in IGNORED_DIRS]
        root = Path(root)
        for filename in files:
            path = root.joinpath(filename)
            try:
                result = scan_file(path)
            except Exception:
                logger.exception(
                    "Unexpected exception when scanning file %s", path
                )
                continue
            if result is not None:
                yield result
