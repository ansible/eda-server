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

from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from aap_eda.core import enums, models
from aap_eda.core.utils.delete_log_util import create_audit_trail
from aap_eda.tasks.log_cleanup import _purge_old_log_records


@pytest.fixture
def activation_with_logs(
    default_decision_environment: models.DecisionEnvironment,
    default_project: models.Project,
    default_rulebook: models.Rulebook,
    default_extra_var_data: str,
    default_organization: models.Organization,
    default_user: models.User,
):
    activation = models.Activation.objects.create(
        name="test-activation",
        decision_environment=default_decision_environment,
        project=default_project,
        rulebook=default_rulebook,
        extra_var=default_extra_var_data,
        organization=default_organization,
        user=default_user,
    )

    instance = models.RulebookProcess.objects.create(
        name="test-instance",
        activation=activation,
        git_hash=default_project.git_hash,
        status=enums.ActivationStatus.RUNNING,
        status_message=enums.ACTIVATION_STATUS_MESSAGE_MAP[
            enums.ActivationStatus.RUNNING
        ],
        organization=default_organization,
    )

    now = timezone.now()

    old_logs = models.RulebookProcessLog.objects.bulk_create(
        [
            models.RulebookProcessLog(
                log=f"old log line {i}",
                activation_instance=instance,
                log_timestamp=int((now - timedelta(days=45 - i)).timestamp()),
            )
            for i in range(5)
        ]
    )

    recent_logs = models.RulebookProcessLog.objects.bulk_create(
        [
            models.RulebookProcessLog(
                log=f"recent log line {i}",
                activation_instance=instance,
                log_timestamp=int((now - timedelta(days=5 - i)).timestamp()),
            )
            for i in range(5)
        ]
    )

    return {
        "activation": activation,
        "instance": instance,
        "old_logs": old_logs,
        "recent_logs": recent_logs,
    }


@pytest.mark.django_db
@override_settings(LOG_RETENTION_DAYS=30)
def test_purge_deletes_old_logs(activation_with_logs):
    assert models.RulebookProcessLog.objects.count() == 10

    _purge_old_log_records()

    assert models.RulebookProcessLog.objects.count() == 5
    remaining = models.RulebookProcessLog.objects.values_list("log", flat=True)
    for log in remaining:
        assert "recent" in log


@pytest.mark.django_db
@override_settings(LOG_RETENTION_DAYS=30)
def test_purge_preserves_recent_logs(activation_with_logs):
    recent_ids = {log.id for log in activation_with_logs["recent_logs"]}

    _purge_old_log_records()

    remaining_ids = set(
        models.RulebookProcessLog.objects.values_list("id", flat=True)
    )
    assert recent_ids == remaining_ids


@pytest.mark.django_db
@override_settings(LOG_RETENTION_DAYS=0)
def test_purge_disabled_when_zero(activation_with_logs):
    _purge_old_log_records()

    assert models.RulebookProcessLog.objects.count() == 10


@pytest.mark.django_db
@override_settings(LOG_RETENTION_DAYS=30)
def test_purge_no_logs_to_delete(
    default_decision_environment,
    default_project,
    default_rulebook,
    default_extra_var_data,
    default_organization,
    default_user,
):
    activation = models.Activation.objects.create(
        name="test-activation",
        decision_environment=default_decision_environment,
        project=default_project,
        rulebook=default_rulebook,
        extra_var=default_extra_var_data,
        organization=default_organization,
        user=default_user,
    )

    instance = models.RulebookProcess.objects.create(
        name="test-instance",
        activation=activation,
        git_hash=default_project.git_hash,
        status=enums.ActivationStatus.RUNNING,
        status_message=enums.ACTIVATION_STATUS_MESSAGE_MAP[
            enums.ActivationStatus.RUNNING
        ],
        organization=default_organization,
    )

    now = timezone.now()
    models.RulebookProcessLog.objects.create(
        log="recent log",
        activation_instance=instance,
        log_timestamp=int((now - timedelta(days=1)).timestamp()),
    )

    _purge_old_log_records()

    assert models.RulebookProcessLog.objects.count() == 1


@pytest.mark.django_db
def test_create_audit_trail_all_instances(activation_with_logs):
    instance = activation_with_logs["instance"]
    cutoff = timezone.now() - timedelta(days=30)

    count = create_audit_trail(cutoff)

    assert count == 1
    audit_log = models.RulebookProcessLog.objects.filter(
        activation_instance=instance,
        log__contains="were purged at",
    )
    assert audit_log.count() == 1


@pytest.mark.django_db
def test_create_audit_trail_scoped_by_activation_id(activation_with_logs):
    activation = activation_with_logs["activation"]
    cutoff = timezone.now() - timedelta(days=30)

    count = create_audit_trail(
        cutoff,
        activation_ids=[activation.id],
    )

    assert count == 1
    audit_log = models.RulebookProcessLog.objects.filter(
        log__contains="were purged at",
    )
    assert audit_log.count() == 1


@pytest.mark.django_db
def test_create_audit_trail_scoped_by_name(activation_with_logs):
    activation = activation_with_logs["activation"]
    cutoff = timezone.now() - timedelta(days=30)

    count = create_audit_trail(
        cutoff,
        activation_names=[activation.name],
    )

    assert count == 1


@pytest.mark.django_db
def test_create_audit_trail_no_match(activation_with_logs):
    cutoff = timezone.now() - timedelta(days=30)

    count = create_audit_trail(
        cutoff,
        activation_ids=[99999],
    )

    assert count == 0
