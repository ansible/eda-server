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

import uuid

import pytest

from aap_eda.settings.post_load import (
    MAX_PG_IDENTIFIER_LENGTH,
    _normalize_queue_name,
)


@pytest.mark.parametrize(
    "name,expected",
    [
        ("activation", "activation"),
        ("activation-node1", "activation-node1"),
        ("a" * 63, "a" * 63),
        (
            "a" * 64,
            f"eda-{uuid.uuid5(uuid.NAMESPACE_OID, 'a' * 64)}",
        ),
    ],
)
def test_normalize_queue_name(name, expected):
    assert _normalize_queue_name(name) == expected


def test_normalize_queue_name_unique():
    name1 = "eda-" + "a" * 60 + "-node1"
    name2 = "eda-" + "a" * 60 + "-node2"
    assert _normalize_queue_name(name1) != _normalize_queue_name(name2)


def test_normalize_queue_name_idempotent():
    long_name = "x" * 100
    once = _normalize_queue_name(long_name)
    twice = _normalize_queue_name(once)
    assert once == twice


def test_normalize_queue_name_fits_pg_limit():
    result = _normalize_queue_name("x" * 200)
    assert len(result) <= MAX_PG_IDENTIFIER_LENGTH
