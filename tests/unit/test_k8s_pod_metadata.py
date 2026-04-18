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

from aap_eda.api.serializers.activation import (
    _activation_k8s_pod_metadata_payload,
    _normalize_activation_k8s_pod_fields,
)
from aap_eda.core.utils.k8s_pod_metadata import (
    _is_valid_dns_subdomain,
    _validate_qualified_metadata_key,
    validate_k8s_pod_annotations,
    validate_k8s_pod_labels,
)
from aap_eda.core.validators import (
    check_if_k8s_pod_annotations_valid,
    check_if_k8s_pod_labels_valid,
    check_if_k8s_pod_node_selector_valid,
    check_if_k8s_pod_service_account_name_valid,
)

# ---------------------------------------------------------------
# validate_k8s_pod_labels
# ---------------------------------------------------------------


def test_validate_k8s_pod_labels_ok():
    validate_k8s_pod_labels({"team": "payments", "cost-centre": "123"})


def test_validate_k8s_pod_labels_reserved():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_labels({"app": "forbidden"})


def test_validate_k8s_pod_labels_reserved_job_name():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_labels({"job-name": "oops"})


def test_validate_k8s_pod_labels_non_string_value():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_labels({"x": 1})


def test_validate_k8s_pod_labels_rejects_non_object():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_labels("not-a-dict")


def test_validate_k8s_pod_labels_rejects_list():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_labels([])


def test_validate_k8s_pod_labels_rejects_none():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_labels(None)


def test_validate_k8s_pod_labels_rejects_long_unqualified_key():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_labels({"x" * 64: "y"})


def test_validate_k8s_pod_labels_rejects_long_value():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_labels({"k": "v" * 64})


def test_validate_k8s_pod_labels_empty_value_allowed():
    validate_k8s_pod_labels({"tier": ""})


def test_validate_k8s_pod_labels_with_prefix_key():
    validate_k8s_pod_labels({"example.com/tier": "frontend"})


# ---------------------------------------------------------------
# validate_k8s_pod_annotations
# ---------------------------------------------------------------


def test_validate_k8s_pod_annotations_ok():
    validate_k8s_pod_annotations(
        {"eks.amazonaws.com/role-arn": ("arn:aws:iam::123456789012:role/r")}
    )


def test_validate_k8s_pod_annotations_invalid_key():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_annotations({"": "x"})


def test_validate_k8s_pod_annotations_rejects_non_object():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_annotations([])


def test_validate_k8s_pod_annotations_rejects_none():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_annotations(None)


def test_validate_k8s_pod_annotations_rejects_oversized_value():
    huge = "x" * (256 * 1024 + 1)
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_annotations({"example.com/k": huge})


def test_validate_k8s_pod_annotations_allows_large_value():
    limit = 256 * 1024
    validate_k8s_pod_annotations({"example.com/k": "z" * limit})


def test_validate_k8s_pod_annotations_non_string_value():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_annotations({"example.com/k": 42})


def test_validate_k8s_pod_annotations_non_string_key():
    with pytest.raises(serializers.ValidationError):
        validate_k8s_pod_annotations({123: "v"})


# ---------------------------------------------------------------
# _validate_qualified_metadata_key edge cases
# ---------------------------------------------------------------


def test_qualified_key_valid_prefix():
    _validate_qualified_metadata_key("example.com/my-key", field_label="Label")


def test_qualified_key_long_prefix_rejected():
    prefix = "a" * 254
    with pytest.raises(serializers.ValidationError):
        _validate_qualified_metadata_key(f"{prefix}/k", field_label="Label")


def test_qualified_key_long_name_segment_rejected():
    with pytest.raises(serializers.ValidationError):
        _validate_qualified_metadata_key(
            f"example.com/{'n' * 64}", field_label="Label"
        )


def test_qualified_key_empty_prefix_rejected():
    with pytest.raises(serializers.ValidationError):
        _validate_qualified_metadata_key("/name", field_label="Label")


def test_qualified_key_empty_name_rejected():
    with pytest.raises(serializers.ValidationError):
        _validate_qualified_metadata_key("example.com/", field_label="Label")


def test_qualified_key_double_slash_rejected():
    with pytest.raises(serializers.ValidationError):
        _validate_qualified_metadata_key(
            "example.com/a/b", field_label="Label"
        )


def test_qualified_key_invalid_prefix_chars():
    with pytest.raises(serializers.ValidationError):
        _validate_qualified_metadata_key("UPPER.COM/key", field_label="Label")


def test_qualified_key_invalid_name_segment():
    with pytest.raises(serializers.ValidationError):
        _validate_qualified_metadata_key("-bad-start", field_label="Label")


def test_qualified_key_exceeds_253():
    with pytest.raises(serializers.ValidationError):
        _validate_qualified_metadata_key("x" * 254, field_label="Label")


# ---------------------------------------------------------------
# validators.py wrappers (DEPLOYMENT_TYPE gating)
# ---------------------------------------------------------------


@patch("aap_eda.core.validators.settings")
def test_check_sa_valid_skips_non_k8s(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "podman"
    check_if_k8s_pod_service_account_name_valid("any-value")


@patch("aap_eda.core.validators.settings")
def test_check_sa_valid_blank_noop(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    check_if_k8s_pod_service_account_name_valid("")
    check_if_k8s_pod_service_account_name_valid("  ")


@patch("aap_eda.core.validators.settings")
def test_check_sa_valid_accepts_good_name(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    check_if_k8s_pod_service_account_name_valid("my-sa")


@patch("aap_eda.core.validators.settings")
def test_check_sa_valid_rejects_bad_name(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    with pytest.raises(serializers.ValidationError):
        check_if_k8s_pod_service_account_name_valid("INVALID_UPPERCASE")


@patch("aap_eda.core.validators.settings")
def test_check_sa_allowlist_accepts_listed(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    mock_settings.ALLOWED_SERVICE_ACCOUNTS = ["eda-workload", "eda-reader"]
    check_if_k8s_pod_service_account_name_valid("eda-workload")


@patch("aap_eda.core.validators.settings")
def test_check_sa_allowlist_rejects_unlisted(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    mock_settings.ALLOWED_SERVICE_ACCOUNTS = ["eda-workload"]
    with pytest.raises(serializers.ValidationError, match="ALLOWED"):
        check_if_k8s_pod_service_account_name_valid("cluster-admin")


@patch("aap_eda.core.validators.settings")
def test_check_sa_allowlist_empty_allows_any(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    mock_settings.ALLOWED_SERVICE_ACCOUNTS = []
    check_if_k8s_pod_service_account_name_valid("any-sa")


@patch("aap_eda.core.validators.settings")
def test_check_labels_valid_skips_non_k8s(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "podman"
    check_if_k8s_pod_labels_valid({"app": "forbidden"})


@patch("aap_eda.core.validators.settings")
def test_check_labels_valid_none_noop(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    check_if_k8s_pod_labels_valid(None)
    check_if_k8s_pod_labels_valid({})


@patch("aap_eda.core.validators.settings")
def test_check_labels_valid_delegates(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    with pytest.raises(serializers.ValidationError):
        check_if_k8s_pod_labels_valid({"app": "reserved"})


@patch("aap_eda.core.validators.settings")
def test_check_annotations_valid_skips_non_k8s(
    mock_settings,
):
    mock_settings.DEPLOYMENT_TYPE = "podman"
    check_if_k8s_pod_annotations_valid({"": "bad-key"})


@patch("aap_eda.core.validators.settings")
def test_check_annotations_valid_none_noop(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    check_if_k8s_pod_annotations_valid(None)
    check_if_k8s_pod_annotations_valid({})


@patch("aap_eda.core.validators.settings")
def test_check_annotations_valid_delegates(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    with pytest.raises(serializers.ValidationError):
        check_if_k8s_pod_annotations_valid({"": "bad"})


# ---------------------------------------------------------------
# check_if_k8s_pod_node_selector_valid
# ---------------------------------------------------------------


@patch("aap_eda.core.validators.settings")
def test_check_node_selector_skips_non_k8s(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "podman"
    check_if_k8s_pod_node_selector_valid({"bad": 123})


@patch("aap_eda.core.validators.settings")
def test_check_node_selector_none_noop(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    check_if_k8s_pod_node_selector_valid(None)
    check_if_k8s_pod_node_selector_valid({})


@patch("aap_eda.core.validators.settings")
def test_check_node_selector_valid(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    check_if_k8s_pod_node_selector_valid({"kubernetes.io/os": "linux"})


@patch("aap_eda.core.validators.settings")
def test_check_node_selector_rejects_non_dict(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    with pytest.raises(serializers.ValidationError):
        check_if_k8s_pod_node_selector_valid("not-a-dict")


@patch("aap_eda.core.validators.settings")
def test_check_node_selector_rejects_non_string_value(mock_settings):
    mock_settings.DEPLOYMENT_TYPE = "k8s"
    with pytest.raises(serializers.ValidationError):
        check_if_k8s_pod_node_selector_valid({"key": 42})


# ---------------------------------------------------------------
# _normalize_activation_k8s_pod_fields
# ---------------------------------------------------------------


def test_normalize_trims_service_account():
    data = {"k8s_pod_service_account_name": "  my-sa  "}
    _normalize_activation_k8s_pod_fields(data)
    assert data["k8s_pod_service_account_name"] == "my-sa"


def test_normalize_blank_sa_becomes_none():
    data = {"k8s_pod_service_account_name": "   "}
    _normalize_activation_k8s_pod_fields(data)
    assert data["k8s_pod_service_account_name"] is None


def test_normalize_none_sa_stays_none():
    data = {"k8s_pod_service_account_name": None}
    _normalize_activation_k8s_pod_fields(data)
    assert data["k8s_pod_service_account_name"] is None


def test_normalize_none_labels_becomes_empty_dict():
    data = {"k8s_pod_labels": None}
    _normalize_activation_k8s_pod_fields(data)
    assert data["k8s_pod_labels"] == {}


def test_normalize_none_annotations_becomes_empty_dict():
    data = {"k8s_pod_annotations": None}
    _normalize_activation_k8s_pod_fields(data)
    assert data["k8s_pod_annotations"] == {}


def test_normalize_trims_label_keys_and_values():
    data = {"k8s_pod_labels": {"  team ": " ops "}}
    _normalize_activation_k8s_pod_fields(data)
    assert data["k8s_pod_labels"] == {"team": "ops"}


def test_normalize_trims_annotation_keys_and_values():
    data = {"k8s_pod_annotations": {"  example.com/k ": " v "}}
    _normalize_activation_k8s_pod_fields(data)
    assert data["k8s_pod_annotations"] == {"example.com/k": "v"}


def test_normalize_preserves_non_string_label_values():
    data = {"k8s_pod_labels": {"count": 42}}
    _normalize_activation_k8s_pod_fields(data)
    assert data["k8s_pod_labels"]["count"] == 42


def test_normalize_rejects_empty_label_key():
    data = {"k8s_pod_labels": {"  ": "v"}}
    with pytest.raises(serializers.ValidationError):
        _normalize_activation_k8s_pod_fields(data)


def test_normalize_rejects_empty_annotation_key():
    data = {"k8s_pod_annotations": {"  ": "v"}}
    with pytest.raises(serializers.ValidationError):
        _normalize_activation_k8s_pod_fields(data)


def test_normalize_none_node_selector_becomes_empty_dict():
    data = {"k8s_pod_node_selector": None}
    _normalize_activation_k8s_pod_fields(data)
    assert data["k8s_pod_node_selector"] == {}


def test_normalize_trims_node_selector_keys_and_values():
    data = {"k8s_pod_node_selector": {" os ": " linux "}}
    _normalize_activation_k8s_pod_fields(data)
    assert data["k8s_pod_node_selector"] == {"os": "linux"}


def test_normalize_rejects_empty_node_selector_key():
    data = {"k8s_pod_node_selector": {"  ": "v"}}
    with pytest.raises(serializers.ValidationError):
        _normalize_activation_k8s_pod_fields(data)


# ---------------------------------------------------------------
# _activation_k8s_pod_metadata_payload
# ---------------------------------------------------------------


class _FakeActivation:
    def __init__(
        self, sa=None, labels=None, annotations=None, node_selector=None
    ):
        self.k8s_pod_service_account_name = sa
        self.k8s_pod_labels = labels
        self.k8s_pod_annotations = annotations
        self.k8s_pod_node_selector = node_selector


def test_payload_helper_none_fields():
    result = _activation_k8s_pod_metadata_payload(_FakeActivation())
    assert result["k8s_pod_service_account_name"] is None
    assert result["k8s_pod_labels"] == {}
    assert result["k8s_pod_annotations"] == {}
    assert result["k8s_pod_node_selector"] == {}


def test_payload_helper_populated_fields():
    result = _activation_k8s_pod_metadata_payload(
        _FakeActivation(
            sa="my-sa",
            labels={"team": "x"},
            annotations={"example.com/k": "v"},
            node_selector={"kubernetes.io/os": "linux"},
        )
    )
    assert result["k8s_pod_service_account_name"] == "my-sa"
    assert result["k8s_pod_labels"] == {"team": "x"}
    assert result["k8s_pod_annotations"] == {"example.com/k": "v"}
    assert result["k8s_pod_node_selector"] == {"kubernetes.io/os": "linux"}


# ---------------------------------------------------------------
# _is_valid_dns_subdomain
# ---------------------------------------------------------------


def test_dns_subdomain_valid():
    assert _is_valid_dns_subdomain("example.com") is True
    assert _is_valid_dns_subdomain("a") is True
    assert _is_valid_dns_subdomain("my-host.example.io") is True


def test_dns_subdomain_invalid():
    assert _is_valid_dns_subdomain("") is False
    assert _is_valid_dns_subdomain("x" * 254) is False
    assert _is_valid_dns_subdomain("UPPER.COM") is False
    assert _is_valid_dns_subdomain("-bad.com") is False
