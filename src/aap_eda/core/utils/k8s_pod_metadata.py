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

"""Helpers for validating Kubernetes pod template metadata on activations.

Validates label and annotation keys as Kubernetes qualified names (optional
DNS subdomain prefix, slash, then name segment) and label values per core
Kubernetes constraints so invalid objects fail API validation early.
"""

import re

from rest_framework import serializers

# Keys EDA sets on activation job pods for selectors and routing.
RESERVED_POD_LABEL_KEYS = frozenset({"app", "job-name"})

# Name segment: up to 63 chars; alnum, '-', '_', '.'; must start/end alnum.
_NAME_SEGMENT = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9_.-]{0,61}[a-zA-Z0-9])?$")
# DNS subdomain for optional key prefix (lowercase RFC 1123 style).
_DNS_SUBDOMAIN = re.compile(
    r"^[a-z0-9]([-a-z0-9.]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9.]*[a-z0-9])?)*$"
)
_LABEL_VALUE_MAX_LEN = 63
_ANNOTATION_VALUE_MAX_LEN = 256 * 1024


def _validate_qualified_metadata_key(key: str, *, field_label: str) -> None:
    """Reject invalid qualified names for label or annotation keys."""
    if len(key) > 253:
        raise serializers.ValidationError(
            f"{field_label} key {key!r} exceeds maximum length 253"
        )
    if "/" in key:
        prefix, name = key.split("/", 1)
        if not prefix or not name or "/" in name:
            raise serializers.ValidationError(
                f"{field_label} key {key!r} must be a single optional "
                "DNS prefix followed by '/' and a name segment"
            )
        if len(prefix) > 253:
            raise serializers.ValidationError(
                f"{field_label} key prefix for {key!r} exceeds maximum length"
            )
        if len(name) > 63:
            raise serializers.ValidationError(
                f"{field_label} name segment for key {key!r} exceeds 63 "
                "characters"
            )
        if not _DNS_SUBDOMAIN.match(prefix):
            raise serializers.ValidationError(
                f"{field_label} key {key!r} has an invalid DNS subdomain "
                "prefix"
            )
        if not _NAME_SEGMENT.match(name):
            raise serializers.ValidationError(
                f"{field_label} key {key!r} has an invalid name segment"
            )
    else:
        if len(key) > 63:
            raise serializers.ValidationError(
                f"{field_label} key {key!r} exceeds 63 characters (use "
                "prefix/name for longer logical keys)"
            )
        if not _NAME_SEGMENT.match(key):
            raise serializers.ValidationError(
                f"{field_label} key {key!r} is not a valid Kubernetes name"
            )


def _validate_label_value(key: str, value: str) -> None:
    """Validate a label value (empty string is allowed)."""
    if value == "":
        return
    if len(value) > _LABEL_VALUE_MAX_LEN:
        raise serializers.ValidationError(
            f"Label value for key {key!r} exceeds maximum length "
            f"{_LABEL_VALUE_MAX_LEN}"
        )
    if not _NAME_SEGMENT.match(value):
        raise serializers.ValidationError(
            f"Label value for key {key!r} is not a valid Kubernetes "
            "label value"
        )


def validate_k8s_pod_labels(data: dict) -> None:
    """Validate user-supplied pod labels (string keys and string values)."""
    if not isinstance(data, dict):
        raise serializers.ValidationError(
            "k8s_pod_labels must be a JSON object"
        )

    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise serializers.ValidationError(
                "k8s_pod_labels keys and values must be strings"
            )
        if key in RESERVED_POD_LABEL_KEYS:
            raise serializers.ValidationError(
                f"Label key {key!r} is reserved by Event-Driven Ansible"
            )
        _validate_qualified_metadata_key(key, field_label="Label")
        _validate_label_value(key, value)


def validate_k8s_pod_annotations(data: dict) -> None:
    """Validate user-supplied pod annotations (string keys and values)."""
    if not isinstance(data, dict):
        raise serializers.ValidationError(
            "k8s_pod_annotations must be a JSON object"
        )

    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise serializers.ValidationError(
                "k8s_pod_annotations keys and values must be strings"
            )
        if len(key) > 253:
            raise serializers.ValidationError(
                f"Annotation key {key!r} exceeds maximum length 253"
            )
        _validate_qualified_metadata_key(key, field_label="Annotation")
        if len(value) > _ANNOTATION_VALUE_MAX_LEN:
            raise serializers.ValidationError(
                f"Annotation value for key {key!r} exceeds maximum length "
                f"{_ANNOTATION_VALUE_MAX_LEN}"
            )
