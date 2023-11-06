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

from aap_eda.services.activation.engine.ports import find_ports


def test_ports():
    rulebook = """
---
- name: Run a webhook service
  hosts: all
  sources:
    - ansible.eda.webhook:
        host: 0.0.0.0
        port: 5555
"""
    ports = find_ports(rulebook)

    assert ports == [("0.0.0.0", 5555)]


def test_ports_with_multi_sources():
    rulebook = """
---
- name: Run a webhook service
  hosts: all
  sources:
    - ansible.eda.webhook1:
        host: 0.0.0.0
        port: 5555
    - ansible.eda.webhook2:
        host: 127.0.0.1
        port: 8888
"""
    ports = find_ports(rulebook)

    assert ports == [("0.0.0.0", 5555), ("127.0.0.1", 8888)]


def test_ports_without_host():
    rulebook = """
---
- name: Run a webhook service
  hosts: all
  sources:
    - ansible.eda.webhook:
        port: 5555
"""
    ports = find_ports(rulebook)

    assert ports == [(None, 5555)]


def test_ports_without_port():
    rulebook = """
---
- name: Run a webhook service
  hosts: all
  sources:
    - ansible.eda.webhook:
        host: 0.0.0.0
"""
    ports = find_ports(rulebook)

    assert ports == []


def test_ports_with_empty_plugin():
    rulebook = """
---
- name: Run a webhook service
  hosts: all
  sources:
    - ansible.eda.webhook:
"""
    ports = find_ports(rulebook)

    assert ports == []
