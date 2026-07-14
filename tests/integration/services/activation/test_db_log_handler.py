#  Copyright 2025 Red Hat, Inc.
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

import pytest
from django.test import override_settings

from aap_eda.core import enums, models
from aap_eda.services.activation.db_log_handler import DBLogger


@pytest.fixture
def rulebook_process(
    default_decision_environment: models.DecisionEnvironment,
    default_project: models.Project,
    default_rulebook: models.Rulebook,
    default_extra_var_data: str,
    default_organization: models.Organization,
    default_user: models.User,
) -> models.RulebookProcess:
    activation = models.Activation.objects.create(
        name="test-activation",
        decision_environment=default_decision_environment,
        project=default_project,
        rulebook=default_rulebook,
        extra_var=default_extra_var_data,
        organization=default_organization,
        user=default_user,
    )

    return models.RulebookProcess.objects.create(
        name="test-instance",
        activation=activation,
        git_hash=default_project.git_hash,
        status=enums.ActivationStatus.RUNNING,
        status_message=enums.ACTIVATION_STATUS_MESSAGE_MAP[
            enums.ActivationStatus.RUNNING
        ],
        organization=default_organization,
    )


@pytest.mark.django_db
@override_settings(
    ANSIBLE_RULEBOOK_FLUSH_AFTER="end",
    MAX_LOG_LINES_PER_INSTANCE=10,
)
def test_enforce_max_log_lines_trims_oldest(rulebook_process):
    logger = DBLogger(rulebook_process.id)

    for i in range(15):
        logger.write(f"log line {i}", flush=False)

    logger.flush()

    assert (
        models.RulebookProcessLog.objects.filter(
            activation_instance=rulebook_process,
        ).count()
        == 10
    )

    remaining = list(
        models.RulebookProcessLog.objects.filter(
            activation_instance=rulebook_process,
        )
        .order_by("id")
        .values_list("log", flat=True)
    )
    assert remaining[0] == "log line 5"
    assert remaining[-1] == "log line 14"


@pytest.mark.django_db
@override_settings(
    ANSIBLE_RULEBOOK_FLUSH_AFTER="end",
    MAX_LOG_LINES_PER_INSTANCE=0,
)
def test_enforce_max_log_lines_disabled_when_zero(rulebook_process):
    logger = DBLogger(rulebook_process.id)

    for i in range(20):
        logger.write(f"log line {i}", flush=False)

    logger.flush()

    assert (
        models.RulebookProcessLog.objects.filter(
            activation_instance=rulebook_process,
        ).count()
        == 20
    )


@pytest.mark.django_db
@override_settings(
    ANSIBLE_RULEBOOK_FLUSH_AFTER="end",
    MAX_LOG_LINES_PER_INSTANCE=50,
)
def test_enforce_max_log_lines_no_trim_when_under_cap(rulebook_process):
    logger = DBLogger(rulebook_process.id)

    for i in range(10):
        logger.write(f"log line {i}", flush=False)

    logger.flush()

    assert (
        models.RulebookProcessLog.objects.filter(
            activation_instance=rulebook_process,
        ).count()
        == 10
    )


@pytest.mark.django_db
@override_settings(
    ANSIBLE_RULEBOOK_FLUSH_AFTER="end",
    MAX_LOG_LINES_PER_INSTANCE=10,
)
def test_enforce_max_log_lines_preserves_newest(rulebook_process):
    logger = DBLogger(rulebook_process.id)

    for i in range(25):
        logger.write(f"line {i}", flush=False)

    logger.flush()

    remaining = list(
        models.RulebookProcessLog.objects.filter(
            activation_instance=rulebook_process,
        )
        .order_by("id")
        .values_list("log", flat=True)
    )
    assert len(remaining) == 10
    assert remaining == [f"line {i}" for i in range(15, 25)]
