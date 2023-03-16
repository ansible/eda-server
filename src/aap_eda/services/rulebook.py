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

from aap_eda.core import models


def expand_ruleset_sources(rulebook_data: dict) -> dict:
    # TODO(cutwater): Docstring needed
    # TODO(cutwater): Tests needed
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


def insert_rulebook_related_data(
    rulebook: models.Rulebook, data: dict
) -> None:
    expanded_sources = expand_ruleset_sources(data)

    rule_sets = [
        models.Ruleset(
            rulebook=rulebook,
            name=data["name"],
            sources=expanded_sources.get(data["name"]),
        )
        for data in (data or [])
    ]
    rule_sets = models.Ruleset.objects.bulk_create(rule_sets)

    rules = [
        models.Rule(name=rule["name"], action=rule["action"], ruleset=rule_set)
        for rule_set, rule_set_data in zip(rule_sets, data)
        for rule in rule_set_data["rules"]
    ]
    models.Rule.objects.bulk_create(rules)


def get_ruleset_project(ruleset: int):
    rulebook = models.Rulebook.objects.get(id=ruleset)
    return rulebook.project


def get_ruleset_rule_count(data_id: int) -> int:
    rule_count = models.Rule.objects.filter(ruleset_id=data_id).count()
    return rule_count


def build_ruleset_list(data: models.Ruleset):
    ruleset_id = data.id
    data.rule_count = get_ruleset_rule_count(ruleset_id)
    data.fired_stats = build_fired_stats(data)

    return data


def build_ruleset_details(data: models.Ruleset):
    ruleset_id = data.id
    data.project = get_ruleset_project(data.rulebook.id)
    data.source_types = [src["type"] for src in (data.sources)]
    data.rule_count = get_ruleset_rule_count(ruleset_id)
    data.fired_stats = build_fired_stats(data)

    return data


# TODO: define when audit rules/rulesets are available
def build_fired_stats(ruleset_data: dict) -> list[dict]:
    return [{}]
