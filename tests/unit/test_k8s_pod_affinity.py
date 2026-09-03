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
from unittest.mock import patch

import pytest
from rest_framework import serializers

from aap_eda.core.validators import check_if_k8s_pod_affinity_valid


@patch("aap_eda.core.validators.settings")
def test_affinity_skips_non_k8s(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "podman"
    check_if_k8s_pod_affinity_valid({"bogus": "value"})


@patch("aap_eda.core.validators.settings")
def test_affinity_none_noop(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    check_if_k8s_pod_affinity_valid(None)


@patch("aap_eda.core.validators.settings")
def test_affinity_empty_dict_noop(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    check_if_k8s_pod_affinity_valid({})


@patch("aap_eda.core.validators.settings")
def test_affinity_valid_node_affinity(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    check_if_k8s_pod_affinity_valid(
        {
            "nodeAffinity": {
                "requiredDuringSchedulingIgnoredDuringExecution": {
                    "nodeSelectorTerms": [
                        {
                            "matchExpressions": [
                                {
                                    "key": "eda-lab/zone",
                                    "operator": "In",
                                    "values": ["a"],
                                }
                            ]
                        }
                    ]
                }
            }
        }
    )


@patch("aap_eda.core.validators.settings")
def test_affinity_valid_multiple_top_level_keys(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    check_if_k8s_pod_affinity_valid(
        {
            "nodeAffinity": {
                "preferredDuringSchedulingIgnoredDuringExecution": []
            },
            "podAffinity": {
                "preferredDuringSchedulingIgnoredDuringExecution": []
            },
            "podAntiAffinity": {
                "preferredDuringSchedulingIgnoredDuringExecution": []
            },
        }
    )


@patch("aap_eda.core.validators.settings")
def test_affinity_not_a_dict(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    with pytest.raises(serializers.ValidationError, match="JSON object"):
        check_if_k8s_pod_affinity_valid(["not-a-dict"])


@patch("aap_eda.core.validators.settings")
def test_affinity_unknown_top_level_key(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    with pytest.raises(
        serializers.ValidationError, match="unknown top-level keys"
    ):
        check_if_k8s_pod_affinity_valid({"bogusAffinity": {}})


@patch("aap_eda.core.validators.settings")
def test_affinity_sub_value_not_a_dict(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    with pytest.raises(serializers.ValidationError, match="JSON object"):
        check_if_k8s_pod_affinity_valid({"nodeAffinity": "not-a-dict"})
