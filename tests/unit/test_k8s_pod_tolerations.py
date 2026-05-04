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

from aap_eda.core.validators import validate_k8s_pod_tolerations


class TestValidateK8sPodTolerations:
    def test_empty_list(self):
        validate_k8s_pod_tolerations([])

    def test_valid_toleration_equal(self):
        validate_k8s_pod_tolerations(
            [
                {
                    "key": "dedicated",
                    "operator": "Equal",
                    "value": "eda",
                    "effect": "NoSchedule",
                }
            ]
        )

    def test_valid_toleration_exists(self):
        validate_k8s_pod_tolerations(
            [{"key": "dedicated", "operator": "Exists"}]
        )

    def test_valid_toleration_exists_with_effect(self):
        validate_k8s_pod_tolerations(
            [
                {
                    "key": "node.kubernetes.io/not-ready",
                    "operator": "Exists",
                    "effect": "NoExecute",
                    "tolerationSeconds": 300,
                }
            ]
        )

    def test_valid_multiple_tolerations(self):
        validate_k8s_pod_tolerations(
            [
                {
                    "key": "team",
                    "operator": "Equal",
                    "value": "platform",
                    "effect": "NoSchedule",
                },
                {
                    "key": "node.kubernetes.io/unreachable",
                    "operator": "Exists",
                    "effect": "NoExecute",
                    "tolerationSeconds": 60,
                },
            ]
        )

    def test_valid_toleration_lt_operator(self):
        validate_k8s_pod_tolerations(
            [
                {
                    "key": "node.kubernetes.io/memory-pressure",
                    "operator": "Lt",
                    "value": "100",
                    "effect": "NoSchedule",
                }
            ]
        )

    def test_valid_toleration_gt_operator(self):
        validate_k8s_pod_tolerations(
            [
                {
                    "key": "node.kubernetes.io/disk-pressure",
                    "operator": "Gt",
                    "value": "50",
                }
            ]
        )

    def test_valid_empty_effect(self):
        validate_k8s_pod_tolerations(
            [
                {
                    "key": "dedicated",
                    "operator": "Equal",
                    "value": "eda",
                    "effect": "",
                }
            ]
        )

    def test_valid_toleration_match_all_taints(self):
        validate_k8s_pod_tolerations([{"operator": "Exists"}])

    def test_valid_toleration_defaults(self):
        validate_k8s_pod_tolerations([{"key": "example"}])

    def test_not_a_list(self):
        with pytest.raises(serializers.ValidationError, match="JSON array"):
            validate_k8s_pod_tolerations({"key": "val"})

    def test_item_not_a_dict(self):
        with pytest.raises(serializers.ValidationError, match="JSON object"):
            validate_k8s_pod_tolerations(["not-a-dict"])

    def test_unknown_keys(self):
        with pytest.raises(serializers.ValidationError, match="unknown keys"):
            validate_k8s_pod_tolerations([{"key": "x", "bogus": "y"}])

    def test_invalid_operator(self):
        with pytest.raises(serializers.ValidationError, match="operator"):
            validate_k8s_pod_tolerations([{"key": "x", "operator": "In"}])

    def test_invalid_effect(self):
        with pytest.raises(serializers.ValidationError, match="effect"):
            validate_k8s_pod_tolerations(
                [{"key": "x", "effect": "DoNotSchedule"}]
            )

    def test_exists_with_value_rejected(self):
        with pytest.raises(
            serializers.ValidationError, match="must not be set"
        ):
            validate_k8s_pod_tolerations(
                [
                    {
                        "key": "x",
                        "operator": "Exists",
                        "value": "oops",
                    }
                ]
            )

    def test_toleration_seconds_not_int(self):
        with pytest.raises(serializers.ValidationError, match="integer"):
            validate_k8s_pod_tolerations(
                [
                    {
                        "key": "x",
                        "effect": "NoExecute",
                        "tolerationSeconds": "300",
                    }
                ]
            )

    def test_toleration_seconds_bool_rejected(self):
        with pytest.raises(serializers.ValidationError, match="integer"):
            validate_k8s_pod_tolerations(
                [
                    {
                        "key": "x",
                        "effect": "NoExecute",
                        "tolerationSeconds": True,
                    }
                ]
            )

    def test_toleration_seconds_wrong_effect(self):
        with pytest.raises(serializers.ValidationError, match="NoExecute"):
            validate_k8s_pod_tolerations(
                [
                    {
                        "key": "x",
                        "effect": "NoSchedule",
                        "tolerationSeconds": 60,
                    }
                ]
            )

    def test_key_not_string(self):
        with pytest.raises(serializers.ValidationError, match="key must be"):
            validate_k8s_pod_tolerations([{"key": 123}])

    def test_value_not_string(self):
        with pytest.raises(serializers.ValidationError, match="value must be"):
            validate_k8s_pod_tolerations(
                [{"key": "x", "operator": "Equal", "value": 42}]
            )

    def test_empty_key_requires_exists(self):
        with pytest.raises(
            serializers.ValidationError, match="'Exists' when key is empty"
        ):
            validate_k8s_pod_tolerations(
                [{"key": "", "operator": "Equal", "value": "v"}]
            )

    def test_missing_key_requires_exists(self):
        with pytest.raises(
            serializers.ValidationError, match="'Exists' when key is empty"
        ):
            validate_k8s_pod_tolerations([{"operator": "Equal", "value": "v"}])
