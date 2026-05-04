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

import os
from unittest import mock

import pytest

from aap_eda.services.activation.engine.exceptions import (
    ContainerEngineInitError,
)
from aap_eda.services.activation.engine.kubernetes import Engine


@mock.patch.dict("os.environ", {"EDA_ACTIVATION_JOB_NAMESPACE": "eda-jobs"})
def test_set_namespace_env_override():
    engine = Engine(
        activation_id="1",
        resource_prefix="activation",
        client=mock.Mock(),
    )
    assert engine.namespace == "eda-jobs"


@mock.patch.dict(
    "os.environ", {"EDA_ACTIVATION_JOB_NAMESPACE": "  eda-jobs  "}
)
def test_set_namespace_env_override_strips_whitespace():
    engine = Engine(
        activation_id="1",
        resource_prefix="activation",
        client=mock.Mock(),
    )
    assert engine.namespace == "eda-jobs"


@mock.patch.dict("os.environ", {"EDA_ACTIVATION_JOB_NAMESPACE": ""})
def test_set_namespace_empty_env_falls_back_to_file():
    with mock.patch("builtins.open", mock.mock_open(read_data="aap-eda")):
        engine = Engine(
            activation_id="1",
            resource_prefix="activation",
            client=mock.Mock(),
        )
        assert engine.namespace == "aap-eda"


def test_set_namespace_unset_env_falls_back_to_file():
    env = {
        k: v
        for k, v in os.environ.items()
        if k != "EDA_ACTIVATION_JOB_NAMESPACE"
    }
    with mock.patch.dict("os.environ", env, clear=True):
        with mock.patch(
            "builtins.open",
            mock.mock_open(read_data="my-namespace"),
        ):
            engine = Engine(
                activation_id="1",
                resource_prefix="activation",
                client=mock.Mock(),
            )
            assert engine.namespace == "my-namespace"


@mock.patch.dict("os.environ", {"EDA_ACTIVATION_JOB_NAMESPACE": "   "})
def test_set_namespace_whitespace_only_env_falls_back_to_file():
    with mock.patch("builtins.open", mock.mock_open(read_data="aap-eda")):
        engine = Engine(
            activation_id="1",
            resource_prefix="activation",
            client=mock.Mock(),
        )
        assert engine.namespace == "aap-eda"


def test_set_namespace_no_env_no_file_raises():
    with mock.patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ContainerEngineInitError):
            Engine(
                activation_id="1",
                resource_prefix="activation",
                client=mock.Mock(),
            )
