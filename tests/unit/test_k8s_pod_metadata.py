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
from rest_framework import serializers

from aap_eda.core.utils.k8s_pod_metadata import (
    validate_k8s_pod_annotations,
    validate_k8s_pod_labels,
)


def test_validate_k8s_pod_labels_ok():
    validate_k8s_pod_labels({"team": "payments", "cost-centre": "123"})


def test_validate_k8s_pod_labels_reserved():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_labels({"app": "forbidden"})


def test_validate_k8s_pod_labels_non_string_value():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_labels({"x": 1})


def test_validate_k8s_pod_labels_rejects_non_object():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_labels("not-a-dict")


def test_validate_k8s_pod_labels_rejects_long_unqualified_key():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_labels({"x" * 64: "y"})


def test_validate_k8s_pod_labels_rejects_long_value():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_labels({"k": "v" * 64})


def test_validate_k8s_pod_annotations_ok():
    validate_k8s_pod_annotations(
        {"eks.amazonaws.com/role-arn": "arn:aws:iam::123456789012:role/r"}
    )


def test_validate_k8s_pod_annotations_invalid_key():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_annotations({"": "x"})


def test_validate_k8s_pod_annotations_rejects_non_object():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_annotations([])


def test_validate_k8s_pod_annotations_rejects_oversized_value():
    huge = "x" * (256 * 1024 + 1)
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_annotations({"example.com/k": huge})


def test_validate_k8s_pod_annotations_allows_large_value_within_limit():
    limit = 256 * 1024
    validate_k8s_pod_annotations({"example.com/k": "z" * limit})
