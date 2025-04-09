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

from importlib.metadata import PackageNotFoundError, version
from unittest.mock import patch

import pytest
from django.db import models
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from rest_framework import serializers

from aap_eda.core.utils.strings import extract_variables
from aap_eda.utils import (
    get_package_version,
    logger as utils_logger,
    str_to_bool,
)
from aap_eda.utils.openapi import generate_query_params


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("True", True),
        ("False", False),
        ("false", False),
        ("yes", True),
        ("no", False),
        ("1", True),
        ("0", False),
        ("", False),
        ("anything", False),
    ],
)
def test_str_to_bool(value, expected):
    assert str_to_bool(value) == expected


def test_get_package_version(caplog_factory):
    eda_caplog = caplog_factory(utils_logger)
    assert get_package_version("aap-eda") == version("aap-eda")
    assert get_package_version("podman") == version("podman")

    # assert outcome when package is not found
    with patch("importlib.metadata.version", side_effect=PackageNotFoundError):
        assert get_package_version("aap-eda") == "unknown"
        assert "returning 'unknown' version" in eda_caplog.text


@pytest.mark.parametrize(
    "value,expected",
    [
        ("simple", set()),
        (
            "And this is a {{demo}}",
            {
                "demo",
            },
        ),
        (
            "{{var1}} and {{var2}}",
            {
                "var1",
                "var2",
            },
        ),
    ],
)
def test_extract_variables(value, expected):
    assert extract_variables(value) == expected


#################################################################
# Tests for src/aap_eda/utils/openapi.py
#################################################################
class AnotherSampleModel(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "tests"


class SampleModel(models.Model):
    name = models.CharField(max_length=100)
    age = models.IntegerField()
    created_at = models.DateField()
    is_active = models.BooleanField()
    another_model = models.ForeignKey(
        AnotherSampleModel, on_delete=models.CASCADE, null=True
    )
    secret = models.CharField(max_length=100)

    class Meta:
        app_label = "tests"


class SampleModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = SampleModel
        fields = [
            "id",
            "name",
            "age",
            "created_at",
            "is_active",
            "another_model_id",
        ]


@pytest.mark.parametrize(
    "serializer, expected_params",
    [
        (
            SampleModelSerializer(),
            [
                OpenApiParameter(
                    name="id",
                    description="Filter by id",
                    required=False,
                    type=OpenApiTypes.NUMBER,
                ),
                OpenApiParameter(
                    name="name",
                    description="Filter by name",
                    required=False,
                    type=OpenApiTypes.STR,
                ),
                OpenApiParameter(
                    name="age",
                    description="Filter by age",
                    required=False,
                    type=OpenApiTypes.NUMBER,
                ),
                OpenApiParameter(
                    name="created_at",
                    description="Filter by created_at",
                    required=False,
                    type=OpenApiTypes.DATETIME,
                ),
                OpenApiParameter(
                    name="is_active",
                    description="Filter by is_active",
                    required=False,
                    type=OpenApiTypes.BOOL,
                ),
                OpenApiParameter(
                    name="another_model_id",
                    description="Filter by another_model_id",
                    required=False,
                    type=OpenApiTypes.STR,
                ),
            ],
        ),
    ],
)
def test_generate_query_params(serializer, expected_params):
    query_params = generate_query_params(serializer)

    assert isinstance(query_params, list)
    assert len(query_params) == len(expected_params)

    for param, expected in zip(query_params, expected_params):
        assert param.__dict__ == expected.__dict__
