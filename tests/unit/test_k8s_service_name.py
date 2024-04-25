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
    InvalidRFC1035LabelError,
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


@pytest.mark.django_db
def test_create_k8s_service_name():
    activation = "good-name"
    service_name = create_k8s_service_name(activation)
    assert service_name == activation

    upper_activation = "Upper  space..dot_A"
    service_name = create_k8s_service_name(upper_activation)
    assert service_name == "upper--space--dot-a"

    invalid_activation = "33_abcdefghijklm"
    with pytest.raises(InvalidRFC1035LabelError):
        create_k8s_service_name(invalid_activation)
