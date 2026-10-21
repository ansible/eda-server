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

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, transaction
from django.test import override_settings
from django.utils import timezone

from aap_eda.core import enums, models


@pytest.fixture
def prepare_log_records(
    default_decision_environment: models.DecisionEnvironment,
    default_project: models.Project,
    default_rulebook: models.Rulebook,
    default_extra_var_data: str,
    default_organization: models.Organization,
    default_user: models.User,
) -> list[models.Activation]:
    activation_30_days_ago = models.Activation.objects.create(
        name="activation-30-days-ago",
        description="Activation 30 days ago",
        decision_environment=default_decision_environment,
        project=default_project,
        rulebook=default_rulebook,
        extra_var=default_extra_var_data,
        organization=default_organization,
        user=default_user,
        log_level="debug",
    )

    instances_30_days_ago = models.RulebookProcess.objects.bulk_create(
        [
            models.RulebookProcess(
                name="activation-30-days-ago-instance-1",
                activation=activation_30_days_ago,
                git_hash=default_project.git_hash,
                status=enums.ActivationStatus.STOPPED,
                status_message=enums.ACTIVATION_STATUS_MESSAGE_MAP[
                    enums.ActivationStatus.STOPPED
                ],
                organization=default_organization,
            ),
            models.RulebookProcess(
                name="activation-30-days-ago-instance-2",
                activation=activation_30_days_ago,
                git_hash=default_project.git_hash,
                status=enums.ActivationStatus.FAILED,
                status_message=enums.ACTIVATION_STATUS_MESSAGE_MAP[
                    enums.ActivationStatus.FAILED
                ],
                organization=default_organization,
            ),
        ]
    )

    activation_10_days_ago = models.Activation.objects.create(
        name="activation-10-days-ago",
        description="Activation 10 days ago",
        decision_environment=default_decision_environment,
        project=default_project,
        rulebook=default_rulebook,
        extra_var=default_extra_var_data,
        organization=default_organization,
        user=default_user,
        log_level="debug",
    )

    instances_10_days_ago = models.RulebookProcess.objects.bulk_create(
        [
            models.RulebookProcess(
                name="activation-10-days-ago-instance-1",
                activation=activation_10_days_ago,
                git_hash=default_project.git_hash,
                status=enums.ActivationStatus.COMPLETED,
                status_message=enums.ACTIVATION_STATUS_MESSAGE_MAP[
                    enums.ActivationStatus.COMPLETED
                ],
                organization=default_organization,
            ),
            models.RulebookProcess(
                name="activation-10-days-ago-instance-2",
                activation=activation_10_days_ago,
                git_hash=default_project.git_hash,
                status=enums.ActivationStatus.RUNNING,
                status_message=enums.ACTIVATION_STATUS_MESSAGE_MAP[
                    enums.ActivationStatus.RUNNING
                ],
                organization=default_organization,
            ),
        ]
    )

    log_timestamp_10_days_ago = timezone.now() - timedelta(days=10)
    log_timestamp_30_days_ago = timezone.now() - timedelta(days=30)

    models.RulebookProcessLog.objects.bulk_create(
        [
            models.RulebookProcessLog(
                log="activation-instance-30-days-ago-log-1",
                activation_instance=instances_30_days_ago[0],
                log_timestamp=int(log_timestamp_30_days_ago.timestamp()),
            ),
            models.RulebookProcessLog(
                log="activation-instance-30-days-ago-log-2",
                activation_instance=instances_30_days_ago[0],
                log_timestamp=int(log_timestamp_30_days_ago.timestamp()),
            ),
            models.RulebookProcessLog(
                log="activation-instance-30-days-ago-log-3",
                activation_instance=instances_30_days_ago[1],
                log_timestamp=int(log_timestamp_30_days_ago.timestamp()),
            ),
            models.RulebookProcessLog(
                log="activation-instance-30-days-ago-log-4",
                activation_instance=instances_30_days_ago[1],
                log_timestamp=int(log_timestamp_30_days_ago.timestamp()),
            ),
            models.RulebookProcessLog(
                log="activation-instance-10-days-ago-log-1",
                activation_instance=instances_10_days_ago[0],
                log_timestamp=int(log_timestamp_10_days_ago.timestamp()),
            ),
            models.RulebookProcessLog(
                log="activation-instance-10-days-ago-log-2",
                activation_instance=instances_10_days_ago[0],
                log_timestamp=int(log_timestamp_10_days_ago.timestamp()),
            ),
            models.RulebookProcessLog(
                log="activation-instance-10-days-ago-log-3",
                activation_instance=instances_10_days_ago[1],
                log_timestamp=int(log_timestamp_10_days_ago.timestamp()),
            ),
            models.RulebookProcessLog(
                log="activation-instance-10-days-ago-log-4",
                activation_instance=instances_10_days_ago[1],
                log_timestamp=int(log_timestamp_10_days_ago.timestamp()),
            ),
        ]
    )

    return [activation_30_days_ago, activation_10_days_ago]


@pytest.mark.django_db
def test_purge_log_records_invalid_date():
    with pytest.raises(CommandError):
        call_command("purge_log_records", "--date", "not-a-date")


@pytest.mark.django_db
@override_settings(ACTIVATION_DB_LOG_RETENTION_DAYS=0)
def test_purge_log_records_no_date_retention_disabled(capsys):
    call_command("purge_log_records")
    captured = capsys.readouterr()
    assert "nothing to purge" in captured.out


@pytest.mark.django_db
@override_settings(ACTIVATION_DB_LOG_RETENTION_DAYS=15)
def test_purge_log_records_defaults_to_retention_days(
    prepare_log_records, capsys
):
    assert models.RulebookProcessLog.objects.count() == 8

    call_command("purge_log_records")

    captured = capsys.readouterr()
    assert "Purged 4 log records" in captured.out
    assert models.RulebookProcessLog.objects.count() == 4


@pytest.mark.django_db
def test_purge_log_records_with_nonexist_activation(capsys):
    args = ("--activation-ids", "42", "--date", "2024-10-01")
    call_command("purge_log_records", *args)
    captured = capsys.readouterr()

    assert (
        "No log records found older than 2024-10-01" in captured.out
        or "Purged" in captured.out
    )


@pytest.mark.parametrize(
    "cutoff_days, expected_remaining",
    [(15, 4), (5, 0)],
)
@pytest.mark.django_db
def test_purge_log_records_with_date(
    prepare_log_records, capsys, cutoff_days, expected_remaining
):
    assert models.RulebookProcessLog.objects.count() == 8

    ts = timezone.now() - timedelta(days=cutoff_days)
    date_str = ts.strftime("%Y-%m-%d")

    call_command("purge_log_records", "--date", date_str)

    assert models.RulebookProcessLog.objects.count() == expected_remaining
    assert "Purged" in capsys.readouterr().out


@pytest.mark.django_db
def test_purge_log_records_with_audit_trail(prepare_log_records, capsys):
    activations = prepare_log_records
    assert models.RulebookProcessLog.objects.count() == 8

    ts = timezone.now() - timedelta(days=15)
    date_str = ts.strftime("%Y-%m-%d")

    call_command(
        "purge_log_records",
        "--date",
        date_str,
        "--audit-trail",
        "--activation-ids",
        str(activations[0].id),
        str(activations[1].id),
    )

    captured = capsys.readouterr()

    assert "Purged" in captured.out
    assert "audit trail" in captured.out

    audit_logs = models.RulebookProcessLog.objects.filter(
        log__contains="were purged at"
    )
    assert audit_logs.count() == 4

    original_logs = models.RulebookProcessLog.objects.exclude(
        log__contains="purged"
    )
    assert original_logs.count() == 4


@pytest.mark.django_db
def test_purge_log_records_without_audit_trail(prepare_log_records, capsys):
    assert models.RulebookProcessLog.objects.count() == 8

    ts = timezone.now() - timedelta(days=5)
    date_str = ts.strftime("%Y-%m-%d")

    call_command("purge_log_records", "--date", date_str)

    captured = capsys.readouterr()

    assert "Purged" in captured.out
    assert "audit trail" not in captured.out

    assert models.RulebookProcessLog.objects.count() == 0


@pytest.fixture
def null_activation_test_data(
    default_organization,
    default_user,
    default_project,
    default_decision_environment,
    default_rulebook,
):
    """Setup test data including a RulebookProcess with NULL activation."""

    activation = models.Activation.objects.create(
        name="test-activation-null-bug",
        description="Test activation",
        decision_environment=default_decision_environment,
        project=default_project,
        rulebook=default_rulebook,
        extra_var={},
        organization=default_organization,
        user=default_user,
        log_level="debug",
    )

    normal_process = models.RulebookProcess.objects.create(
        name="normal-process-null-test",
        activation=activation,
        status=enums.ActivationStatus.STOPPED,
        organization=default_organization,
    )

    with transaction.atomic():
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO core_rulebook_process
            (name, status, git_hash, parent_type, started_at,
             organization_id, activation_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
            [
                "null-activation-process-test",
                enums.ActivationStatus.STOPPED,
                "",
                enums.ProcessParentType.ACTIVATION,
                timezone.now(),
                default_organization.id,
                None,
            ],
        )

    null_process = models.RulebookProcess.objects.get(
        name="null-activation-process-test"
    )

    old_timestamp = timezone.now() - timedelta(days=20)

    models.RulebookProcessLog.objects.bulk_create(
        [
            models.RulebookProcessLog(
                log="Normal process log for null test 1",
                activation_instance=normal_process,
                log_timestamp=int(old_timestamp.timestamp()),
            ),
            models.RulebookProcessLog(
                log="Normal process log for null test 2",
                activation_instance=normal_process,
                log_timestamp=int(old_timestamp.timestamp()),
            ),
            models.RulebookProcessLog(
                log="NULL activation process log for null test 1",
                activation_instance=null_process,
                log_timestamp=int(old_timestamp.timestamp()),
            ),
            models.RulebookProcessLog(
                log="NULL activation process log for null test 2",
                activation_instance=null_process,
                log_timestamp=int(old_timestamp.timestamp()),
            ),
        ]
    )

    return {
        "activation": activation,
        "normal_process": normal_process,
        "null_process": null_process,
    }


@pytest.mark.django_db
def test_purge_without_activation_filter_handles_null_correctly(
    null_activation_test_data, capsys
):
    initial_log_count = models.RulebookProcessLog.objects.filter(
        log__contains="for null test"
    ).count()
    assert initial_log_count == 4

    cutoff_date = (timezone.now() - timedelta(days=10)).strftime("%Y-%m-%d")

    call_command("purge_log_records", "--date", cutoff_date)

    remaining_test_logs = models.RulebookProcessLog.objects.filter(
        log__contains="for null test"
    )
    assert remaining_test_logs.count() == 0
    captured = capsys.readouterr()
    assert "Purged" in captured.out


@pytest.mark.django_db
def test_purge_with_audit_trail_includes_null_activation(
    null_activation_test_data, capsys
):
    cutoff_date = (timezone.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    activation_id = null_activation_test_data["activation"].id

    call_command(
        "purge_log_records",
        "--activation-ids",
        str(activation_id),
        "--date",
        cutoff_date,
        "--audit-trail",
    )

    captured = capsys.readouterr()

    remaining_test_logs = models.RulebookProcessLog.objects.filter(
        log__contains="for null test"
    ).exclude(log__contains="purged")
    assert remaining_test_logs.count() == 0

    assert "Purged" in captured.out
    assert "audit trail" in captured.out


@pytest.mark.django_db
def test_purge_with_audit_trail_by_name_includes_null(
    null_activation_test_data, capsys
):
    cutoff_date = (timezone.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    activation_name = null_activation_test_data["activation"].name

    call_command(
        "purge_log_records",
        "--activation-names",
        activation_name,
        "--date",
        cutoff_date,
        "--audit-trail",
    )

    captured = capsys.readouterr()

    remaining_test_logs = models.RulebookProcessLog.objects.filter(
        log__contains="for null test"
    ).exclude(log__contains="purged")
    assert remaining_test_logs.count() == 0

    assert "Purged" in captured.out
    assert "audit trail" in captured.out
