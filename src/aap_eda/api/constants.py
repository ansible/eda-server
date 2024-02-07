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

# EDA_SERVER_VAULT_LABEL is reserved for system vault password identifiers
EDA_SERVER_VAULT_LABEL = "EDA_SERVER"

PG_NOTIFY_TEMPLATE_RULEBOOK_NAME = "_PG_NOTIFY_TEMPLATE_RULEBOOK_"
PG_NOTIFY_TEMPLATE_RULEBOOK_DATA = """
---
- name: PG Notify Template Event Stream
  hosts: all
  sources:
    - name: my_range
      ansible.eda.range:
        limit: 5
      complementary_source:
        type: ansible.eda.pg_listener
        name: Postgres Listener
        args:
          dsn: "{{ EDA_PG_NOTIFY_DSN }}"
          channels:
            - "{{ EDA_PG_NOTIFY_CHANNEL }}"
      extra_vars:
        EDA_PG_NOTIFY_DSN: "{{ settings.PG_NOTIFY_DSN }}"
        EDA_PG_NOTIFY_CHANNEL: "{{ event_stream.channel_name }}"
      encrypt_vars:
        - EDA_PG_NOTIFY_DSN
  rules:
    - name: Post event
      condition: true
      action:
        pg_notify:
          dsn: "{{ EDA_PG_NOTIFY_DSN }}"
          channel: "{{ EDA_PG_NOTIFY_CHANNEL }}"
          event: "{{ event }}"
"""
