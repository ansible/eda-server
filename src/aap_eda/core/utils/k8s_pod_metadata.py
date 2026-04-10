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

"""Helpers for validating Kubernetes pod template metadata on activations."""

import re

from rest_framework import serializers

# Keys EDA sets on activation job pods for selectors and routing.
RESERVED_POD_LABEL_KEYS = frozenset({"app", "job-name"})

# Rough limits aligned with Kubernetes validation.
_LABEL_KEY_PATTERN = re.compile(
    r"^([A-Za-z0-9]([-A-Za-z0-9_.]*[A-Za-z0-9])?"
    r"(\.[A-Za-z0-9]([-A-Za-z0-9_.]*[A-Za-z0-9])?)*/)?"
    r"([A-Za-z0-9]([-A-Za-z0-9_.]*[A-Za-z0-9])?)$"
)
_LABEL_VALUE_MAX_LEN = 63
_ANNOTATION_VALUE_MAX_LEN = 256 * 1024


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
        if len(key) > 253:
            raise serializers.ValidationError(
                f"Label key {key!r} exceeds maximum length 253"
            )
        if len(value) > _LABEL_VALUE_MAX_LEN:
            raise serializers.ValidationError(
                f"Label value for key {key!r} exceeds maximum length "
                f"{_LABEL_VALUE_MAX_LEN}"
            )
        if not _LABEL_KEY_PATTERN.match(key):
            raise serializers.ValidationError(
                f"Label key {key!r} is not a valid Kubernetes label name"
            )


def validate_k8s_pod_annotations(data: dict) -> None:
    """Validate user-supplied pod annotations."""
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
        if len(value) > _ANNOTATION_VALUE_MAX_LEN:
            raise serializers.ValidationError(
                f"Annotation value for key {key!r} exceeds maximum length "
                f"{_ANNOTATION_VALUE_MAX_LEN}"
            )
        if not _LABEL_KEY_PATTERN.match(key):
            raise serializers.ValidationError(
                f"Annotation key {key!r} is not a valid Kubernetes name"
            )
