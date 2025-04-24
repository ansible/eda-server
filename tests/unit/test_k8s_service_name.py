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

import pytest

from aap_eda.core.utils.k8s_service_name import (
    create_k8s_service_name,
    is_rfc_1035_compliant,
)


@pytest.mark.parametrize(
    ("name", "expect"),
    [
        (
            "abcdefghijklmnopqrstuvwxyz--abcdefghijklmnopqrstuvwxyzabcdefghi",
            True,
        ),
        ("a-test-value89", True),
        (
            "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijkl",
            False,
        ),
        ("A-test-value", False),
        ("a_test_value", False),
        ("a.test.value", False),
        ("89a-test-value", False),
    ],
)
def test_rfc_1035_compliant(name, expect):
    assert is_rfc_1035_compliant(name) is expect


@pytest.mark.parametrize(
    ("name", "service"),
    [
        ("good-name", "good-name"),
        ("Upper [a] space..(dot)_A", "upper-a-space-dot-a"),
        ("33_abcdefghijklm--", "abcdefghijklm"),
        (
            "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz",  # noqa: E501
            "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghi-z",
        ),
    ],
)
@pytest.mark.django_db
def test_create_k8s_service_name(name, service):
    service_name = create_k8s_service_name(name)
    assert service_name == service
    assert is_rfc_1035_compliant(service_name)


def test_create_k8s_service_name_empty():
    service_name = create_k8s_service_name("[]")
    assert service_name.startswith("service-")
    assert is_rfc_1035_compliant(service_name)
