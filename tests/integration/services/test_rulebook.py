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
import yaml

from aap_eda.services.rulebook import (
    DEFAULT_SOURCE_NAME_PREFIX,
    build_source_list,
)


def test_single_source_with_full_parameters():
    single_source = """
---
- name: Test sample 001
  hosts: all
  sources:
      - name: my source
        ansible.eda.range:
          limit: 5
          delay: 1
        filters:
          - noop:
""".strip()

    sources = yaml.safe_load(single_source)
    results = build_source_list(sources)

    assert len(results) == 1
    assert results[0]["name"] == "my source"
    assert results[0]["type"] == "ansible.eda.range"
    assert results[0]["args"] == {"limit": 5, "delay": 1}
    assert results[0].keys() == {"name", "type", "args"}


def test_single_source_1():
    single_source = """
---
- name: Test sample 001
  hosts: all
  sources:
    - ansible.eda.generic:
        event_delay: 1
        payload:
          - user: "Rick"
            universe: C-137
            hosts:
              - eda_localhost2

          - user: "Morty"
            universe: C-137

          - user: "Rick"
            universe: C-132

          - user: "Rick"
            universe: J-19-Zeta-1

          - user: "Beth"
            universe: K-22

          - user: "Jerry"
            universe: C-137
""".strip()
    sources = yaml.safe_load(single_source)
    results = build_source_list(sources)

    assert len(results) == 1
    assert results[0]["name"] == f"{DEFAULT_SOURCE_NAME_PREFIX}1"
    assert results[0]["type"] == "ansible.eda.generic"
    assert results[0]["args"].keys() == {"event_delay", "payload"}
    assert results[0].keys() == {"name", "type", "args"}


def test_single_source_without_name():
    single_source = """
---
- name: Test sample 001
  hosts: all
  sources:
    - ansible.eda.range:
        limit: 5
        delay: 1
      filters:
        - noop:
""".strip()

    sources = yaml.safe_load(single_source)
    results = build_source_list(sources)

    assert len(results) == 1
    assert results[0]["name"] == f"{DEFAULT_SOURCE_NAME_PREFIX}1"
    assert results[0]["type"] == "ansible.eda.range"
    assert results[0]["args"] == {"limit": 5, "delay": 1}
    assert results[0].keys() == {"name", "type", "args"}


def test_multiple_sources():
    sources = """
---
- name: Test sample 001
  hosts: all
  sources:
    - name: my source
      ansible.eda.range:
        limit: 5
        delay: 1
      filters:
        - noop:
    - name: my 2nd source
      ansible.eda.generic:
        event_delay: 1
        payload:
          - user: "Rick"
            universe: C-137
""".strip()

    sources = yaml.safe_load(sources)
    results = build_source_list(sources)

    assert len(results) == 2
    assert results[0]["name"] == "my source"
    assert results[0]["type"] == "ansible.eda.range"
    assert results[0]["args"] == {"limit": 5, "delay": 1}
    assert results[1]["name"] == "my 2nd source"
    assert results[1]["type"] == "ansible.eda.generic"
    assert results[1]["args"] == {
        "event_delay": 1,
        "payload": [{"universe": "C-137", "user": "Rick"}],
    }


def test_multiple_sources_without_names():
    sources = """
---
- name: Test sample 001
  hosts: all
  sources:
    - ansible.eda.range:
        limit: 5
        delay: 1
      filters:
        - noop:
    - ansible.eda.range:
        limit: 6
        delay: 2
      filters:
        - noop:
""".strip()

    sources = yaml.safe_load(sources)
    results = build_source_list(sources)

    assert len(results) == 2
    assert results[0]["name"] == f"{DEFAULT_SOURCE_NAME_PREFIX}1"
    assert results[1]["name"] == f"{DEFAULT_SOURCE_NAME_PREFIX}2"


def test_duplicate_sources():
    sources = """
---
- name: Test sample 001
  hosts: all
  sources:
    - name: my source
      ansible.eda.range:
        limit: 5
        delay: 1
      filters:
        - noop:
    - name: my source
      ansible.eda.range:
        limit: 5
        delay: 1
      filters:
        - noop:
""".strip()

    sources = yaml.safe_load(sources)
    results = build_source_list(sources)

    assert len(results) == 2
    assert results[0]["name"] == "my source"
    assert results[1]["name"] == "my source #2"


def test_duplicate_sources_with_different_names():
    sources = """
---
- name: Test sample 001
  hosts: all
  sources:
    - ansible.eda.range:
        limit: 5
        delay: 1
      filters:
        - noop:
    - name: my source
      ansible.eda.range:
        limit: 5
        delay: 1
      filters:
        - noop:
""".strip()

    sources = yaml.safe_load(sources)
    results = build_source_list(sources)

    assert len(results) == 2
    assert results[0]["name"] == f"{DEFAULT_SOURCE_NAME_PREFIX}1"
    assert results[1]["name"] == "my source"


def test_multple_rulesets():
    sources = """
---
- name: Test sample 001
  hosts: all
  sources:
    - name: my source
      ansible.eda.range:
        limit: 5
        delay: 1
      filters:
        - noop:
- name: Run a webhook listener service
  hosts: all
  sources:
    - ansible.eda.webhook:
  rules:
    - name: Webhook event
      condition: event.payload.ping == "pong"
      action:
        debug:
          msg: "Webhook triggered!"

    - name: Shutdown
      condition: event.payload.shutdown is defined
      action:
        shutdown:
""".strip()

    sources = yaml.safe_load(sources)
    results = build_source_list(sources)

    assert len(results) == 2
    assert results[0]["name"] == "my source"
    assert results[0]["type"] == "ansible.eda.range"
    assert results[0]["args"] == {"limit": 5, "delay": 1}
    assert results[1]["name"] == f"{DEFAULT_SOURCE_NAME_PREFIX}2"
    assert results[1]["type"] == "ansible.eda.webhook"
    assert results[1]["args"] == {}


def test_multple_rulesets_with_duplicate_sources():
    sources = """
---
- name: Test sample 001
  hosts: all
  sources:
    - name: my source
      ansible.eda.range:
        limit: 5
        delay: 1
      filters:
        - noop:
- name: Test sample 002
  hosts: all
  sources:
    - name: my source
      ansible.eda.range:
        limit: 5
        delay: 1
      filters:
        - noop:
""".strip()

    sources = yaml.safe_load(sources)
    results = build_source_list(sources)

    assert len(results) == 1
    assert results[0]["name"] == "my source"
    assert results[0]["type"] == "ansible.eda.range"
    assert results[0]["args"] == {"limit": 5, "delay": 1}
