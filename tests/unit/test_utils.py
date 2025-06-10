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

import tempfile
from importlib.metadata import PackageNotFoundError, version
from unittest.mock import patch

import pytest
from django.db import models
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from rest_framework import serializers

from aap_eda.core.utils import safe_yaml
from aap_eda.core.utils.strings import extract_variables
from aap_eda.utils import (
    get_package_version,
    logger as utils_logger,
    sanitize_postgres_identifier,
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


@pytest.mark.parametrize(
    "input_str,expected_output",
    [
        ("valid_name", "valid_name"),
        ("Valid123", "Valid123"),
        ("_underscore", "_underscore"),
        ("hello-world", "hello_world"),
        ("bad@name!", "bad_name_"),
        ("some space", "some_space"),
        ("123name", "_123name"),
        ("9abc", "_9abc"),
        ("@@@", "____"),
        ("123", "_123"),
        ("a" * 63, "a" * 63),
        (("1" + "a" * 61), ("_1" + "a" * 61)),
    ],
)
def test_sanitize_postgres_identifier_valid_cases(input_str, expected_output):
    assert sanitize_postgres_identifier(input_str) == expected_output


def test_empty_identifier_raises():
    with pytest.raises(ValueError, match="Identifier cannot be empty."):
        sanitize_postgres_identifier("")


def test_identifier_exceeding_length_limit_raises():
    too_long = "a" * 64
    with pytest.raises(ValueError, match="exceeds 63 characters"):
        sanitize_postgres_identifier(too_long)


def test_identifier_with_invalid_first_character_raises():
    too_long = "1" + "a" * 62
    with pytest.raises(ValueError, match="invalid first character"):
        sanitize_postgres_identifier(too_long)


TEST_YAML_DATA = {
    "dict": {"a": "b", "c": "d"},
    "list": ["a", "b", "c"],
    "tuple": ("a", "b", "c"),
    "set": {"a", "b", "c"},
    "num": 300,
}


TEST_YAML_OUTPUT = """dict:
  a: !unsafe 'b'
  c: !unsafe 'd'
list:
- !unsafe 'a'
- !unsafe 'b'
- !unsafe 'c'
num: 300
set: !!set
  !unsafe 'a': null
  !unsafe 'b': null
  !unsafe 'c': null
tuple:
- !unsafe 'a'
- !unsafe 'b'
- !unsafe 'c'
"""


def test_dump_safe_yaml():
    with tempfile.NamedTemporaryFile() as f:
        safe_yaml.dump(f.name, TEST_YAML_DATA)
        with open(f.name) as f:
            assert f.read() == TEST_YAML_OUTPUT


def test_dump_safe_yaml_invalid_type():
    with pytest.raises(TypeError, match="Data must be a dictionary"):
        safe_yaml.dump("test", "test")
