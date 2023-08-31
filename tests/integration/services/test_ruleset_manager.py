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
from unittest import mock

import pytest
from django.conf import settings

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus, RestartPolicy
from aap_eda.services.ruleset.activation_db_logger import ActivationDbLogger
from aap_eda.services.ruleset.k8s_ruleset_handler import K8SRulesetHandler
from aap_eda.services.ruleset.podman_ruleset_handler import (
    PodmanRulesetHandler,
)
from aap_eda.services.ruleset.ruleset_manager import RulesetManager

RULESETS = """
---
- name: hello
  hosts: localhost
  sources:
    - ansible.eda.webhook:
        host: 0.0.0.0
        port: 5000
  gather_facts: false
  tasks:
    - debug:
        msg: hello
"""

EXTRA_VAR = """
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


@pytest.fixture()
def init_data():
    decision_environment = models.DecisionEnvironment.objects.create(
        name="test-de",
        image_url="quay.io/ansible/ansible-rulebook",
        description="test-de-description",
    )
    project = models.Project.objects.create(
        name="test-project",
        url="https://git.example.com/acme/project-01",
        description="test-project-description",
    )
    rulebook = models.Rulebook.objects.create(
        name="test-rulebook",
        rulesets=RULESETS,
        description="test-rulebook-description",
    )
    extra_var = models.ExtraVar.objects.create(
        name="test-extra-var.yml", extra_var=EXTRA_VAR
    )
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    activation = models.Activation.objects.create(
        decision_environment=decision_environment,
        project=project,
        rulebook_rulesets=RULESETS,
        extra_var=extra_var,
        user=user,
    )

    return InitData(
        activation=activation,
        decision_environment=decision_environment,
        project=project,
        rulebook=rulebook,
        extra_var=extra_var,
    )


def test_ruleset_manager_podman_handler():
    settings.DEPLOYMENT_TYPE = "podman"
    manager = RulesetManager()
    assert type(manager.handler) == PodmanRulesetHandler


def test_ruleset_manager_k8s_handler():
    settings.DEPLOYMENT_TYPE = "k8s"
    manager = RulesetManager()
    assert type(manager.handler) == K8SRulesetHandler


@pytest.mark.django_db
@mock.patch("aap_eda.services.ruleset.ruleset_manager.ActivationDbLogger")
@mock.patch("aap_eda.services.ruleset.ruleset_manager.logger.info")
def test_ruleset_manager_activate_complete(
    info_mock: mock.Mock, logger_mock: mock.Mock, init_data
):
    manager = RulesetManager()

    class MyClass:
        def activate_completed(
            self,
            instance: models.ActivationInstance,
            activation_db_logger: ActivationDbLogger,
        ):
            instance.status = ActivationStatus.COMPLETED
            instance.save(update_fields=["status"])

    activation = init_data.activation
    assert activation.status == ActivationStatus.PENDING

    with mock.patch(
        "aap_eda.services.ruleset.podman_ruleset_handler.PodmanRulesetHandler.activate",  # noqa: E501
        new=MyClass.activate_completed,
    ):
        manager.activate(activation)

    activation.refresh_from_db()
    assert (
        models.ActivationInstance.objects.first().status
        == ActivationStatus.COMPLETED
    )
    assert activation.status == ActivationStatus.COMPLETED
    assert models.ActivationInstance.objects.count() == 1

    activation.restart_policy = RestartPolicy.ALWAYS
    activation.is_enabled = True
    activation.save(update_fields=["restart_policy", "is_enabled"])
    msg = (
        f"Activation {activation.name} completed successfully. "
        "Will restart in 0 seconds according to its restart policy"
    )

    with mock.patch(
        "aap_eda.services.ruleset.podman_ruleset_handler.PodmanRulesetHandler.activate",  # noqa: E501
        new=MyClass.activate_completed,
    ):
        manager.activate(activation)

    info_mock.assert_called_once_with(msg)


@pytest.mark.django_db
@mock.patch("aap_eda.services.ruleset.ruleset_manager.ActivationDbLogger")
@mock.patch("aap_eda.services.ruleset.ruleset_manager.logger.error")
def test_ruleset_manager_activate_failed(
    info_mock: mock.Mock, logger_mock: mock.Mock, init_data
):
    manager = RulesetManager()

    class MyClass:
        def activate_failed(
            self,
            instance: models.ActivationInstance,
            activation_db_logger: ActivationDbLogger,
        ):
            instance.status = ActivationStatus.FAILED
            instance.save(update_fields=["status"])

    activation = init_data.activation
    assert activation.status == ActivationStatus.PENDING

    with mock.patch(
        "aap_eda.services.ruleset.podman_ruleset_handler.PodmanRulesetHandler.activate",  # noqa: E501
        new=MyClass.activate_failed,
    ):
        manager.activate(activation)

    activation.refresh_from_db()
    assert (
        models.ActivationInstance.objects.first().status
        == ActivationStatus.FAILED
    )
    assert activation.status == ActivationStatus.FAILED
    assert models.ActivationInstance.objects.count() == 1

    activation.restart_policy = RestartPolicy.ALWAYS
    activation.is_enabled = True
    activation.save(update_fields=["restart_policy", "is_enabled"])
    msg = (
        f"Activation {activation.name} failed: Activation failed. "
        "Will not restart because it is not restartable"
    )

    with mock.patch(
        "aap_eda.services.ruleset.podman_ruleset_handler.PodmanRulesetHandler.activate",  # noqa: E501
        new=MyClass.activate_failed,
    ):
        manager.activate(activation)

    info_mock.assert_has_calls([mock.call(msg), mock.call(msg)])
