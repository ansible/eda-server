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
import os
from dataclasses import dataclass
from unittest import mock

import pytest
from django.conf import settings
from podman.errors import ImageNotFound

from aap_eda.core import models
from aap_eda.services.ruleset.activate_rulesets import (
    ACTIVATION_PATH,
    ActivateRulesets,
)

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
  sources:
    - ansible.eda.webhook:
        host: 0.0.0.0
        port: 5000
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
    settings.PODMAN_SOCKET_URL = "unix://socket_url"


@pytest.fixture()
def init_data(get_activation_stats):
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
        rulebook_rulesets=TEST_RULESETS,
        extra_var=extra_var,
        user=user,
        ruleset_stats=get_activation_stats,
    )

    return InitData(
        activation=activation,
        decision_environment=decision_environment,
        project=project,
        rulebook=rulebook,
        extra_var=extra_var,
    )


@pytest.fixture
def get_activation_stats():
    return {
        "Ruleset 1 Test": {
            "ruleSetName": "Ruleset 1 Test",
            "numberOfRules": 5,
            "rulesTriggered": 10,
        }
    }


@pytest.mark.django_db
@mock.patch("aap_eda.services.ruleset.activate_rulesets.ActivationDbLogger")
@mock.patch("aap_eda.services.ruleset.activate_rulesets.ActivationPodman")
@mock.patch.dict(os.environ, {"DEPLOYMENT_TYPE": "podman"})
def test_rulesets_activate_with_podman(
    my_mock: mock.Mock, logger_mock: mock.Mock, init_data, get_activation_stats
):
    pod_mock = mock.Mock()
    my_mock.return_value = pod_mock
    log_mock = mock.Mock()
    logger_mock.return_value = log_mock

    container_mock = mock.Mock()
    pod_mock.run_worker_mode.return_value = container_mock
    container_mock.logs.return_value = [
        b"test_output_line_1",
        b"test_output_line_2",
    ]

    assert models.ActivationInstance.objects.count() == 0

    ActivateRulesets().activate(activation=init_data.activation)
    assert models.ActivationInstance.objects.count() == 1
    instance = models.ActivationInstance.objects.first()
    activation = models.Activation.objects.get(pk=instance.activation.id)
    assert _get_rules_count(activation.ruleset_stats) == _get_rules_count(
        get_activation_stats
    )

    my_mock.assert_called_once_with(
        init_data.decision_environment, "unix://socket_url", log_mock
    )
    pod_mock.run_worker_mode.assert_called_once_with(
        ws_url=f"{settings.WEBSOCKET_BASE_URL}{ACTIVATION_PATH}",
        ws_ssl_verify=settings.WEBSOCKET_SSL_VERIFY,
        activation_instance=instance,
        heartbeat=settings.RULEBOOK_LIVENESS_CHECK_SECONDS,
        ports={"5000/tcp": 5000},
    )


def _get_rules_count(ruleset_stats):
    rules_count = 0
    rules_fired_count = 0
    for ruleset_stat in ruleset_stats.values():
        rules_count += ruleset_stat["numberOfRules"]
        rules_fired_count += ruleset_stat["rulesTriggered"]

    return rules_count, rules_fired_count


@pytest.mark.django_db
@mock.patch("aap_eda.services.ruleset.activate_rulesets.ActivationDbLogger")
@mock.patch("aap_eda.services.ruleset.activate_rulesets.ActivationPodman")
@mock.patch.dict(os.environ, {"DEPLOYMENT_TYPE": "podman"})
def test_rulesets_activate_with_exception(
    my_mock: mock.Mock, logger_mock: mock.Mock, init_data, get_activation_stats
):
    def image_not_found():
        raise ImageNotFound()

    pod_mock = mock.Mock()
    my_mock.return_value = pod_mock
    log_mock = mock.Mock()
    logger_mock.return_value = log_mock

    pod_mock.run_worker_mode.side_effect = image_not_found

    ActivateRulesets().activate(activation=init_data.activation)

    init_data.activation.refresh_from_db()
    assert init_data.activation.status == "failed"
