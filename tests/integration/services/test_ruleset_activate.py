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
from unittest import mock

import pytest
from django.conf import settings

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus, EDADeployment
from aap_eda.core.utils import utcnow
from aap_eda.services.activation import (
    ACTIVATED_RULESETS,
    ActivationExecution,
    ActivationExecutionFailed,
    pop_tracked_activation,
)

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

TEST_ACTIVATION_INSTANCE = {
    "started_at": None,
    "activation_id": None,
    "ended_at": None,
    "status": ActivationStatus.PENDING,
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

TEST_RULESETS_YAML = """
---
- name: hello
  hosts: localhost
  gather_facts: false
  tasks:
    - debug:
        msg: hello
"""

TEST_RULESETS = {
    "name": "hello",
    "sources": [
        {
            "name": "hello",
            "gather_facts": False,
            "host": "localhost",
            "task": [
                {"debug": {"msg": "hello"}},
            ],
        },
    ],
    "rulebook_id": None,
}

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
        rulesets=TEST_RULESETS_YAML,
        description=TEST_RULEBOOK["description"],
    ).pk
    TEST_RULESETS["rulebook_id"] = rulebook_id
    ruleset_id = models.Ruleset.objects.create(**TEST_RULESETS).pk
    extra_var_id = models.ExtraVar.objects.create(
        name="test-extra-var.yml", extra_var=TEST_EXTRA_VAR
    ).pk

    return {
        "project_id": project_id,
        "rulebook_id": rulebook_id,
        "ruleset_id": ruleset_id,
        "extra_var_id": extra_var_id,
    }


def create_activation(fks: dict):
    activation_data = TEST_ACTIVATION.copy()
    activation_data["project_id"] = fks["project_id"]
    activation_data["rulebook_id"] = fks["rulebook_id"]
    activation_data["extra_var_id"] = fks["extra_var_id"]
    activation = models.Activation(**activation_data)
    activation.save()
    fks["activation_id"] = activation.id

    return activation


def create_activation_instance(fks: dict):
    activation_inst_data = TEST_ACTIVATION_INSTANCE.copy()
    activation_inst_data["started_at"] = utcnow()
    activation_inst_data["activation_id"] = fks["activation_id"]
    activation_instance = models.ActivationInstance(**activation_inst_data)
    activation_instance.save()
    fks["activaation_instance_id"] = activation_instance.id

    return activation_instance


@pytest.mark.django_db
def test_rulesets_activate_local():
    fks = create_activation_related_data()
    create_activation(fks)
    activation_instance = create_activation_instance(fks)

    with mock.patch(
        "aap_eda.services.activation.ActivationExecution._get_local_command",
        return_value=["ls", "-1"],
    ), mock.patch("aap_eda.services.activation.pop_tracked_activation"):
        settings.EDA_DEPLOY_SETTINGS.deployment_type = EDADeployment.LOCAL
        execution = ActivationExecution(activation_instance)
        execution.activate()

    assert activation_instance.id in ACTIVATED_RULESETS
    assert pop_tracked_activation(activation_instance.id) == execution
    assert execution.activation_instance.status == ActivationStatus.COMPLETED


@pytest.mark.django_db
def test_rulesets_activate_local_error():
    fks = create_activation_related_data()
    create_activation(fks)
    activation_instance = create_activation_instance(fks)

    with mock.patch(
        "aap_eda.services.activation.ActivationExecution._get_local_command",
        return_value=["kdljaflkj92945"],
    ):
        settings.EDA_DEPLOY_SETTINGS.deployment_type = EDADeployment.LOCAL
        execution = ActivationExecution(activation_instance)
        with pytest.raises(ActivationExecutionFailed):
            execution.activate()

    assert activation_instance.status == ActivationStatus.FAILED
    assert activation_instance.id not in ACTIVATED_RULESETS
