#  Copyright 2026 Red Hat, Inc.
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
import pytest
import yaml

from aap_eda.core.exceptions import ParseError
from aap_eda.core.utils.rulebook import (
    _get_source_type,
    build_source_list,
    build_source_name_updates,
    rulebook_sources_unchanged,
)

OLD_RULESETS = """---
- name: Test Ruleset
  hosts: all
  sources:
    - ansible.eda.webhook:
        port: 8000
  rules:
    - name: Rule1
      condition: event
      action:
        debug:
          msg: old
...
"""

NEW_RULESETS_RULES_ONLY = """---
- name: Test Ruleset
  hosts: all
  sources:
    - ansible.eda.webhook:
        port: 8000
  rules:
    - name: Rule1
      condition: event
      action:
        debug:
          msg: new
...
"""

NEW_RULESETS_ARGS_CHANGED = """---
- name: Test Ruleset
  hosts: all
  sources:
    - ansible.eda.webhook:
        port: 9000
  rules:
    - name: Rule1
      condition: event
      action:
        debug:
          msg: old
...
"""

NEW_RULESETS_TYPE_CHANGED = """---
- name: Test Ruleset
  hosts: all
  sources:
    - ansible.eda.kafka:
        topic: events
  rules:
    - name: Rule1
      condition: event
      action:
        debug:
          msg: old
...
"""

NEW_RULESETS_FILTER_CHANGED = """---
- name: Test Ruleset
  hosts: all
  sources:
    - ansible.eda.webhook:
        port: 8000
      filters:
        - ansible.eda.json_filter:
            include_keys:
              - payload
  rules:
    - name: Rule1
      condition: event
      action:
        debug:
          msg: old
...
"""

NEW_RULESETS_NAME_ADDED = """---
- name: Test Ruleset
  hosts: all
  sources:
    - ansible.eda.webhook:
        port: 8000
      name: renamed_source
  rules:
    - name: Rule1
      condition: event
      action:
        debug:
          msg: old
...
"""

NEW_RULESETS_SOURCE_ADDED = """---
- name: Test Ruleset
  hosts: all
  sources:
    - ansible.eda.webhook:
        port: 8000
    - ansible.eda.kafka:
        topic: events
  rules:
    - name: Rule1
      condition: event
      action:
        debug:
          msg: old
...
"""


# ------------------------------------------------------------------ #
#  rulebook_sources_unchanged
# ------------------------------------------------------------------ #


def test_rulebook_sources_unchanged_when_only_rules_change():
    assert rulebook_sources_unchanged(OLD_RULESETS, NEW_RULESETS_RULES_ONLY)


def test_rulebook_sources_unchanged_when_args_change():
    assert rulebook_sources_unchanged(OLD_RULESETS, NEW_RULESETS_ARGS_CHANGED)


def test_rulebook_sources_unchanged_when_filter_changes():
    assert rulebook_sources_unchanged(
        OLD_RULESETS, NEW_RULESETS_FILTER_CHANGED
    )


def test_rulebook_sources_unchanged_when_name_added():
    assert rulebook_sources_unchanged(OLD_RULESETS, NEW_RULESETS_NAME_ADDED)


def test_rulebook_sources_changed_when_type_changes():
    assert not rulebook_sources_unchanged(
        OLD_RULESETS, NEW_RULESETS_TYPE_CHANGED
    )


def test_rulebook_sources_changed_when_source_added():
    assert not rulebook_sources_unchanged(
        OLD_RULESETS, NEW_RULESETS_SOURCE_ADDED
    )


def test_rulebook_sources_unchanged_false_for_invalid_yaml():
    assert not rulebook_sources_unchanged("not yaml", OLD_RULESETS)


# ------------------------------------------------------------------ #
#  build_source_name_updates
# ------------------------------------------------------------------ #


def test_build_source_name_updates_no_change():
    updates = build_source_name_updates(OLD_RULESETS, NEW_RULESETS_RULES_ONLY)
    assert updates == {}


def test_build_source_name_updates_name_added():
    updates = build_source_name_updates(OLD_RULESETS, NEW_RULESETS_NAME_ADDED)
    assert updates == {"__SOURCE_1": "renamed_source"}


def test_build_source_name_updates_invalid_yaml():
    updates = build_source_name_updates("not yaml", OLD_RULESETS)
    assert updates == {}


# ------------------------------------------------------------------ #
#  build_source_list
# ------------------------------------------------------------------ #


def test_build_source_list_raises_for_structurally_invalid_yaml():
    with pytest.raises(ParseError):
        build_source_list("not yaml")


def test_build_source_list_raises_for_empty_source():
    rulesets = yaml.dump(
        [{"name": "Test", "hosts": "all", "sources": [{}], "rules": []}]
    )
    with pytest.raises(ParseError):
        build_source_list(rulesets)


def test_build_source_list_raises_for_non_string_name():
    rulesets = """---
- name: Test
  hosts: all
  sources:
    - ansible.eda.webhook:
        port: 8000
      name: []
  rules: []
"""
    with pytest.raises(ParseError):
        build_source_list(rulesets)


# ------------------------------------------------------------------ #
#  _get_source_type
# ------------------------------------------------------------------ #


def test_get_source_type_webhook():
    source = {"ansible.eda.webhook": {"port": 8000}}
    assert _get_source_type(source) == "ansible.eda.webhook"


def test_get_source_type_with_name_and_filters():
    source = {
        "name": "my_source",
        "ansible.eda.kafka": {"topic": "events"},
        "filters": [{"ansible.eda.json_filter": {}}],
    }
    assert _get_source_type(source) == "ansible.eda.kafka"


def test_get_source_type_empty():
    assert _get_source_type({}) is None
