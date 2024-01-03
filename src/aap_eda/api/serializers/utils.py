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

import yaml


def swap_sources(data: str, sources: list[dict]) -> str:
    rulesets = yaml.safe_load(data)
    new_sources = []
    for source in sources:
        src_obj = {"name": source["name"], source["type"]: source["args"]}
        new_sources.append(src_obj)

    for ruleset in rulesets:
        ruleset["sources"] = new_sources

    return yaml.dump(rulesets)
