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
import logging

from aap_eda.core import models
from aap_eda.core.enums import InventorySource

from .common import StrPath
from .scan import EntryKind, ScanResult, scan_project

logger = logging.getLogger(__name__)


def import_files(project: models.Project, path: StrPath):
    for entry in scan_project(path):
        import_file(project, entry)


def import_file(project: models.Project, entry: ScanResult):
    return IMPORT_HANDLERS[entry.kind](project, entry)


def import_inventory(
    project: models.Project, entry: ScanResult
) -> models.Inventory:
    return models.Inventory.objects.create(
        project=project,
        name=entry.filename,
        inventory=entry.raw_content,
        inventory_source=InventorySource.PROJECT,
    )


def import_extra_var(
    project: models.Project, entry: ScanResult
) -> models.ExtraVar:
    return models.ExtraVar.objects.create(
        project=project,
        name=entry.filename,
        extra_var=entry.raw_content,
    )


def import_playbook(
    project: models.Project, entry: ScanResult
) -> models.Playbook:
    return models.Playbook.objects.create(
        project=project,
        name=entry.filename,
        playbook=entry.raw_content,
    )


def import_rulebook(
    project: models.Project, entry: ScanResult
) -> models.Rulebook:
    rulebook = models.Rulebook.objects.create(
        project=project, name=entry.filename
    )

    expanded_sources = expand_ruleset_sources(entry.content)

    rule_sets = [
        models.Ruleset(
            rulebook=rulebook,
            name=data["name"],
            sources=expanded_sources.get(data["name"]),
        )
        for data in (entry.content or [])
    ]
    rule_sets = models.Ruleset.objects.bulk_create(rule_sets)

    rules = [
        models.Rule(name=rule["name"], action=rule["action"], ruleset=rule_set)
        for rule_set, rule_set_data in zip(rule_sets, entry.content)
        for rule in rule_set_data["rules"]
    ]
    models.Rule.objects.bulk_create(rules)

    return rulebook


def expand_ruleset_sources(rulebook_data: dict) -> dict:
    # TODO(cutwater): Docstring needed
    expanded_ruleset_sources = {}
    if rulebook_data is not None:
        for ruleset_data in rulebook_data:
            xp_sources = []
            expanded_ruleset_sources[ruleset_data["name"]] = xp_sources
            for source in ruleset_data.get("sources") or []:
                xp_src = {"name": "<unnamed>"}
                for src_key, src_val in source.items():
                    if src_key == "name":
                        xp_src["name"] = src_val
                    elif src_key == "filters":
                        xp_src["filters"] = src_val
                    else:
                        xp_src["type"] = src_key.split(".")[-1]
                        xp_src["source"] = src_key
                        xp_src["config"] = src_val
                xp_sources.append(xp_src)

    return expanded_ruleset_sources


IMPORT_HANDLERS = {
    EntryKind.INVENTORY: import_inventory,
    EntryKind.EXTRA_VARS: import_extra_var,
    EntryKind.PLAYBOOK: import_playbook,
    EntryKind.RULEBOOK: import_rulebook,
}
