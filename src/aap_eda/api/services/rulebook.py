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

from aap_eda.api import serializers
from aap_eda.core import models


def insert_rulebook_related_data(
    rulebook: models.Rulebook, rulebook_data: dict
) -> None:
    expanded_sources = expand_ruleset_sources(rulebook_data)

    for ruleset_data in rulebook_data or []:
        ruleset = models.Ruleset.objects.create(
            name=ruleset_data["name"],
            rulebook_id=rulebook.id,
            sources=expanded_sources.get(ruleset_data["name"]),
        )
        for rule in ruleset_data["rules"] or []:
            models.Rule.objects.create(
                name=rule["name"],
                action=rule["action"],
                ruleset_id=ruleset.id,
            )


def expand_ruleset_sources(rulebook_data: dict) -> dict:
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


def ruleset_out_data(ruleset: models.Ruleset) -> dict:
    data = serializers.RulesetSerializer(ruleset).data

    data["source_types"] = [src.get("type") for src in (data["sources"] or [])]
    data["rule_count"] = models.Rule.objects.filter(
        ruleset_id=ruleset.id
    ).count()
    data["fired_stats"] = build_fired_stats(data)

    for key in ["rulebook", "sources"]:
        data.pop(key)

    return data


def rule_out_data(rule: models.Rule) -> dict:
    data = serializers.RuleSerializer(rule).data
    data["fired_stats"] = build_fired_stats(data)

    return data


# TODO: define when audit rules/rulesets are available
def build_fired_stats(ruleset_data: dict) -> list[dict]:
    return [{}]
