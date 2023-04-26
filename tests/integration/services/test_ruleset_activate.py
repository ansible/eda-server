#  Copyright 2023 Red Hat, Inc.
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
from dataclasses import dataclass
from subprocess import CompletedProcess
from unittest import mock

import pytest
from django.conf import settings

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.services.ruleset.activate_rulesets import ActivateRulesets

TEST_ACTIVATION = {
    "name": "test-activation",
    "description": "test activation",
    "is_enabled": True,
    "project_id": 1,
    "rulebook_id": 1,
    "extra_var_id": 1,
    "restart_policy": "on-failure",
    "restart_count": 0,
}

TEST_DECISION_ENV = {
    "name": "test-de",
    "image_url": "quay.io/ansible/ansible-rulebook",
    "description": "test de",
}

TEST_PROJECT = {
    "name": "test-project-01",
    "url": "https://git.example.com/acme/project-01",
    "description": "test project",
}

TEST_RULEBOOK = {
    "name": "test-rulebook.yml",
    "description": "test rulebook",
}

TEST_RULESETS = """
---
- name: hello
  hosts: localhost
  gather_facts: false
  tasks:
    - debug:
        msg: hello
"""

TEST_EXTRA_VAR = """
---
collections:
  - community.general
  - benthomasson.eda
"""


@dataclass
class InitData:
    activation: models.Activation
    decision_environment: models.DecisionEnvironment
    project: models.Project
    rulebook: models.Rulebook
    extra_var: models.ExtraVar


@pytest.fixture(autouse=True)
def use_dummy_socket_url(settings):
    settings.EDA_PODMAN_SOCKET_URL = "unix://socket_url"


@pytest.fixture()
def init_data():
    decision_environment = models.DecisionEnvironment.objects.create(
        name=TEST_DECISION_ENV["name"],
        image_url=TEST_DECISION_ENV["image_url"],
        description=TEST_DECISION_ENV["description"],
    )
    project = models.Project.objects.create(
        name=TEST_PROJECT["name"],
        url=TEST_PROJECT["url"],
        description=TEST_PROJECT["description"],
    )
    rulebook = models.Rulebook.objects.create(
        name=TEST_RULEBOOK["name"],
        rulesets=TEST_RULESETS,
        description=TEST_RULEBOOK["description"],
    )
    extra_var = models.ExtraVar.objects.create(
        name="test-extra-var.yml", extra_var=TEST_EXTRA_VAR
    )
    activation = models.Activation.objects.create(
        decision_environment=decision_environment,
        project=project,
        rulebook=rulebook,
        extra_var=extra_var,
    )

    return InitData(
        activation=activation,
        decision_environment=decision_environment,
        project=project,
        rulebook=rulebook,
        extra_var=extra_var,
    )


@pytest.mark.django_db
@mock.patch("subprocess.run")
@mock.patch("shutil.which")
def test_rulesets_activate_local(
    which_mock: mock.Mock, run_mock: mock.Mock, init_data
):
    which_mock.return_value = "/bin/cmd"
    out = "test_output_line_1\ntest_output_line_2"
    run_mock.return_value = CompletedProcess(
        args="command",
        returncode=0,
        stdout=out,
    )

    assert models.ActivationInstanceLog.objects.count() == 0

    ActivateRulesets().activate(
        activation_id=init_data.activation.id,
        decision_environment_id=init_data.decision_environment.id,
        deployment_type="local",
        ws_base_url="ws://localhost:8000",
        ssl_verify="no",
    )

    assert models.ActivationInstanceLog.objects.count() == 2
    assert (
        models.ActivationInstance.objects.first().status
        == ActivationStatus.COMPLETED.value
    )


@pytest.mark.django_db
@mock.patch("subprocess.run")
def test_rulesets_activate_with_errors(run_mock: mock.Mock, init_data):
    assert models.ActivationInstance.objects.count() == 0

    ActivateRulesets().activate(
        activation_id=init_data.activation.id,
        decision_environment_id=init_data.decision_environment.id,
        deployment_type="bad_type",
        ws_base_url="ws://localhost:8000",
        ssl_verify="no",
    )

    assert (
        models.ActivationInstance.objects.first().status
        == ActivationStatus.FAILED.value
    )


@pytest.mark.django_db
@mock.patch("aap_eda.services.ruleset.activate_rulesets.ActivationPodman")
def test_rulesets_activate_with_podman(my_mock: mock.Mock, init_data):
    pod_mock = mock.Mock()
    my_mock.return_value = pod_mock

    container_mock = mock.Mock()
    pod_mock.run_worker_mode.return_value = container_mock
    container_mock.logs.return_value = [
        b"test_output_line_1",
        b"test_output_line_2",
    ]

    assert models.ActivationInstance.objects.count() == 0

    ActivateRulesets().activate(
        activation_id=init_data.activation.id,
        decision_environment_id=init_data.decision_environment.id,
        deployment_type="podman",
        ws_base_url="ws://localhost:8000",
        ssl_verify="no",
    )
    assert models.ActivationInstance.objects.count() == 1
    instance = models.ActivationInstance.objects.first()

    my_mock.assert_called_once_with(init_data.decision_environment, None)
    pod_mock.run_worker_mode.assert_called_once_with(
        ws_url="ws://localhost:8000/api/eda/ws/ansible-rulebook",
        ws_ssl_verify="no",
        activation_instance_id=instance.id,
        heartbeat=str(settings.RULEBOOK_LIVENESS_CHECK_SECONDS),
    )
    assert (
        models.ActivationInstance.objects.first().status
        == ActivationStatus.COMPLETED.value
    )
    assert models.ActivationInstanceLog.objects.count() == 2
