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

# TODO(cutwater): Refactoring needed
#       1. Move into `aap_eda.services` package
#       2. Decouple from API. Services MUST expect parsed data, not raw data.
#       3. Services MUST NOT use serializes for data de-serialization.
#       4. Define public interface.
#       5. Remove duplicated code (`import_rulebook_releated_data` and
#           `import_rulebook` functions).

from aap_eda.api import serializers
from aap_eda.core import models
from aap_eda.services.project.importing import expand_ruleset_sources


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


def ruleset_out_data(ruleset: models.Ruleset) -> dict:
    data = serializers.RulesetSerializer(ruleset).data

    data["source_types"] = [src["type"] for src in (data["sources"] or [])]
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
