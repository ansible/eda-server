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
from subprocess import CompletedProcess
from unittest import mock

import pytest

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.services.ruleset.activate_rulesets import ActivateRulesets

TEST_ACTIVATION = {
    "name": "test-activation",
    "description": "test activation",
    "is_enabled": True,
    "execution_environment": "quay.io/aizquier/ansible-rulebook",
    "project_id": 1,
    "rulebook_id": 1,
    "extra_var_id": 1,
    "restart_policy": "on-failure",
    "restart_count": 0,
}

TEST_PROJECT = {
    "name": "test-project-01",
    "url": "https://git.example.com/acme/project-01",
    "description": "test project",
}

TEST_RULEBOOK = {
    "name": "test-rulebook.yml",
    "description": "test rulebok",
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


def create_activation_related_data():
    project_id = models.Project.objects.create(
        name=TEST_PROJECT["name"],
        url=TEST_PROJECT["url"],
        description=TEST_PROJECT["description"],
    ).pk
    rulebook_id = models.Rulebook.objects.create(
        name=TEST_RULEBOOK["name"],
        rulesets=TEST_RULESETS,
        description=TEST_RULEBOOK["description"],
    ).pk
    extra_var_id = models.ExtraVar.objects.create(
        name="test-extra-var.yml", extra_var=TEST_EXTRA_VAR
    ).pk

    return {
        "project_id": project_id,
        "rulebook_id": rulebook_id,
        "extra_var_id": extra_var_id,
    }


def create_activation(fks: dict):
    activation_data = TEST_ACTIVATION.copy()
    activation_data["project_id"] = fks["project_id"]
    activation_data["rulebook_id"] = fks["rulebook_id"]
    activation_data["extra_var_id"] = fks["extra_var_id"]
    activation = models.Activation(**activation_data)
    activation.save()

    return activation


@pytest.mark.django_db
@mock.patch("subprocess.run")
@mock.patch("shutil.which")
def test_rulesets_activate_local(which_mock: mock.Mock, run_mock: mock.Mock):
    fks = create_activation_related_data()
    activation = create_activation(fks)

    which_mock.return_value = "/bin/cmd"
    out = "test_output_line_1\ntest_output_line_2"
    run_mock.return_value = CompletedProcess(
        args="command",
        returncode=0,
        stdout=out,
    )

    assert models.ActivationInstanceLog.objects.count() == 0

    ActivateRulesets().activate(
        activation_id=activation.id,
        execution_environment="quay.io/ansible-rulebook",
        deployment_type="local",
        host="localhost",
        port="8000",
    )

    assert models.ActivationInstanceLog.objects.count() == 2
    assert (
        models.ActivationInstance.objects.first().status
        == ActivationStatus.COMPLETED.value
    )


@pytest.mark.django_db
@mock.patch("subprocess.run")
def test_rulesets_activate_with_errors(run_mock: mock.Mock):
    fks = create_activation_related_data()
    activation = create_activation(fks)

    assert models.ActivationInstance.objects.count() == 0

    ActivateRulesets().activate(
        activation_id=activation.id,
        execution_environment="quay.io/ansible-rulebook",
        deployment_type="bad_type",
        host="localhost",
        port="8000",
    )

    assert (
        models.ActivationInstance.objects.first().status
        == ActivationStatus.FAILED.value
    )
